#!/usr/bin/env python3
"""음성/동영상 파일 전사 + 화자/인물 분리(한국어 초안).

핵심 기능
- WhisperX 기반 한국어 전사(기본값: ko)
- 화자 분리(옵션, HF 토큰 필요)
- 동영상 인물 자동 구분(옵션): 얼굴 임베딩 클러스터링으로 PERSON 라벨 생성

주의
- 인물 구분은 "누가 화면에 크게 보이는지" 기반의 추정치입니다.
- 진짜 발화자 추적(Active Speaker Detection)과 100% 동일하지 않습니다.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PersonWindow:
    time_sec: float
    person_id: str


def format_draft(segments: list[dict], include_person: bool = True) -> str:
    lines: list[str] = []
    for seg in segments:
        speaker = seg.get("speaker", "SPEAKER_UNKNOWN")
        person = seg.get("person", "PERSON_UNKNOWN") if include_person else None
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        text = (seg.get("text") or "").strip()

        if person is not None:
            lines.append(f"[{start:07.2f} - {end:07.2f}] {speaker} | {person}: {text}")
        else:
            lines.append(f"[{start:07.2f} - {end:07.2f}] {speaker}: {text}")
    return "\n".join(lines)


def _run_ffprobe_duration(input_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def build_person_timeline(input_path: Path, sample_every_sec: float) -> list[PersonWindow]:
    """동영상 프레임에서 얼굴 클러스터링으로 PERSON_XX 타임라인 생성."""
    try:
        import cv2  # type: ignore
        import face_recognition  # type: ignore
        import numpy as np  # type: ignore
        from sklearn.cluster import DBSCAN  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "영상 인물 자동 구분에는 opencv-python, face_recognition, scikit-learn, numpy가 필요합니다."
        ) from exc

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise SystemExit(f"동영상을 열 수 없습니다: {input_path}")

    duration = _run_ffprobe_duration(input_path)
    sample_times = np.arange(0, max(duration, 0.001), sample_every_sec)

    encodings: list = []
    encoding_times: list[float] = []

    for t in sample_times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model="hog")
        if not locations:
            continue

        # 화면에서 가장 큰 얼굴 1개를 대표값으로 사용
        def area(loc: tuple[int, int, int, int]) -> int:
            top, right, bottom, left = loc
            return max(0, bottom - top) * max(0, right - left)

        best_loc = max(locations, key=area)
        face_encs = face_recognition.face_encodings(rgb, [best_loc])
        if not face_encs:
            continue

        encodings.append(face_encs[0])
        encoding_times.append(float(t))

    cap.release()

    if not encodings:
        return []

    x = np.array(encodings)
    labels = DBSCAN(eps=0.55, min_samples=2, metric="euclidean").fit_predict(x)

    windows: list[PersonWindow] = []
    unknown_idx = 0
    for t, lbl in zip(encoding_times, labels):
        if lbl == -1:
            person_id = f"PERSON_UNKNOWN_{unknown_idx:02d}"
            unknown_idx += 1
        else:
            person_id = f"PERSON_{int(lbl):02d}"
        windows.append(PersonWindow(time_sec=t, person_id=person_id))

    windows.sort(key=lambda w: w.time_sec)
    return windows


def assign_person_to_segments(segments: list[dict], windows: list[PersonWindow]) -> list[dict]:
    if not windows:
        for seg in segments:
            seg["person"] = "PERSON_UNAVAILABLE"
        return segments

    for seg in segments:
        mid = (float(seg.get("start", 0.0)) + float(seg.get("end", 0.0))) / 2
        nearest = min(windows, key=lambda w: abs(w.time_sec - mid))
        seg["person"] = nearest.person_id
    return segments


def run(args: argparse.Namespace) -> None:
    try:
        import whisperx  # type: ignore
    except ImportError as exc:
        raise SystemExit("whisperx가 설치되어 있지 않습니다. `pip install whisperx` 후 다시 실행하세요.") from exc

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"입력 파일이 없습니다: {input_path}")

    model = whisperx.load_model(args.model, args.device, compute_type=args.compute_type)
    audio = whisperx.load_audio(str(input_path))
    result = model.transcribe(
        audio,
        batch_size=args.batch_size,
        language=args.language,
        initial_prompt=args.initial_prompt,
    )

    align_model, metadata = whisperx.load_align_model(language_code=result["language"], device=args.device)
    aligned = whisperx.align(result["segments"], align_model, metadata, audio, args.device)

    segments = aligned["segments"]
    if args.hf_token:
        diarize_model = whisperx.DiarizationPipeline(use_auth_token=args.hf_token, device=args.device)
        diarize_result = diarize_model(audio)
        diarized = whisperx.assign_word_speakers(diarize_result, aligned)
        segments = diarized["segments"]

    is_video = input_path.suffix.lower() in {".mp4", ".mov", ".mkv", ".avi", ".webm"}
    if args.enable_video_person and is_video:
        windows = build_person_timeline(input_path, sample_every_sec=args.video_sample_every)
        segments = assign_person_to_segments(segments, windows)

    draft_text = format_draft(segments, include_person=args.enable_video_person and is_video)

    output_txt = Path(args.output)
    output_txt.write_text(draft_text, encoding="utf-8")

    output_json = output_txt.with_suffix(".json")
    output_json.write_text(json.dumps(segments, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"초안 전사 저장: {output_txt}")
    print(f"세그먼트 JSON 저장: {output_json}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="한국어 중심 전사 + 화자/인물 분리 초안 생성")
    parser.add_argument("input", help="입력 음성/동영상 파일 경로")
    parser.add_argument("-o", "--output", default="transcript_draft.txt", help="출력 텍스트 파일")
    parser.add_argument("--model", default="large-v3", help="Whisper 모델명")
    parser.add_argument("--device", default="cpu", help="실행 디바이스: cpu/cuda")
    parser.add_argument("--compute-type", default="int8", help="연산 타입 (예: int8, float16)")
    parser.add_argument("--batch-size", type=int, default=8, help="배치 크기")

    # 한국어 기본값
    parser.add_argument("--language", default="ko", help="전사 언어 코드(기본: ko)")
    parser.add_argument(
        "--initial-prompt",
        default="한국어 회의/인터뷰 전사. 고유명사와 숫자 표기를 최대한 정확히 유지.",
        help="전사 초기 프롬프트",
    )

    # 화자 분리
    parser.add_argument("--hf-token", default="", help="Hugging Face 토큰 (화자 분리용)")

    # 영상 인물 구분
    parser.add_argument(
        "--enable-video-person",
        action="store_true",
        help="동영상에서 얼굴 클러스터링으로 PERSON 라벨 자동 부여",
    )
    parser.add_argument("--video-sample-every", type=float, default=1.0, help="영상 샘플링 간격(초)")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    run(parser.parse_args())
