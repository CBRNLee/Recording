#!/usr/bin/env python3
"""음성/동영상 파일 전사 + 화자 분리(초안).

필수 패키지(예시):
  pip install whisperx

주의:
- 화자 분리를 위해 Hugging Face 토큰이 필요할 수 있습니다.
- 이 스크립트는 초안 생성용이며, 최종 품질 보정을 권장합니다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def format_draft(segments: list[dict]) -> str:
    lines: list[str] = []
    for seg in segments:
        speaker = seg.get("speaker", "SPEAKER_UNKNOWN")
        start = seg.get("start", 0.0)
        end = seg.get("end", 0.0)
        text = (seg.get("text") or "").strip()
        lines.append(f"[{start:07.2f} - {end:07.2f}] {speaker}: {text}")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> None:
    try:
        import whisperx  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "whisperx가 설치되어 있지 않습니다. `pip install whisperx` 후 다시 실행하세요."
        ) from exc

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"입력 파일이 없습니다: {input_path}")

    device = args.device
    batch_size = args.batch_size
    compute_type = args.compute_type

    model = whisperx.load_model(args.model, device, compute_type=compute_type)
    audio = whisperx.load_audio(str(input_path))
    result = model.transcribe(audio, batch_size=batch_size)

    # 단어 단위 정렬
    align_model, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    aligned = whisperx.align(result["segments"], align_model, metadata, audio, device)

    # 화자 분리(선택)
    diarized_segments = aligned["segments"]
    if args.hf_token:
        diarize_model = whisperx.DiarizationPipeline(use_auth_token=args.hf_token, device=device)
        diarize_result = diarize_model(audio)
        diarized = whisperx.assign_word_speakers(diarize_result, aligned)
        diarized_segments = diarized["segments"]

    draft_text = format_draft(diarized_segments)

    output_txt = Path(args.output)
    output_txt.write_text(draft_text, encoding="utf-8")

    output_json = output_txt.with_suffix(".json")
    output_json.write_text(json.dumps(diarized_segments, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"초안 전사 저장: {output_txt}")
    print(f"세그먼트 JSON 저장: {output_json}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="음성/동영상 전사 및 화자 분리 초안 생성")
    parser.add_argument("input", help="입력 음성/동영상 파일 경로")
    parser.add_argument("-o", "--output", default="transcript_draft.txt", help="출력 텍스트 파일")
    parser.add_argument("--model", default="large-v3", help="Whisper 모델명")
    parser.add_argument("--device", default="cpu", help="실행 디바이스: cpu/cuda")
    parser.add_argument("--compute-type", default="int8", help="연산 타입 (예: int8, float16)")
    parser.add_argument("--batch-size", type=int, default=8, help="배치 크기")
    parser.add_argument("--hf-token", default="", help="Hugging Face 토큰 (화자 분리용)")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    run(parser.parse_args())
