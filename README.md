# Recording

한글 전사에 초점을 둔 **음성/동영상 전사 초안 도구**입니다.

## 핵심 기능
- 한국어 기본 전사 (`--language ko` 기본값)
- 화자 분리(다이어라이제이션, 선택)
- 동영상 인물 자동 구분(선택): 얼굴 임베딩 클러스터링으로 `PERSON_XX` 라벨 부여

## 설치
```bash
pip install whisperx
```

영상 인물 자동 구분까지 쓰려면 추가 설치:
```bash
pip install opencv-python face_recognition scikit-learn numpy
# ffmpeg, ffprobe도 시스템에 설치되어 있어야 함
```

## 사용 예시
### 0) 빠른 시연(의존성 없이 출력 포맷 확인)
```bash
python transcribe_draft.py ./anything.wav -o ./demo_draft.txt --demo --enable-video-person
```
> `--demo`는 실제 전사를 수행하지 않고 샘플 결과 파일을 만들어 출력 형식을 확인합니다.

### 1) 한국어 전사(기본)
```bash
python transcribe_draft.py ./sample.wav -o ./sample_draft.txt
```

### 2) 화자 분리 포함
```bash
python transcribe_draft.py ./sample.wav -o ./sample_draft.txt --hf-token YOUR_HF_TOKEN
```

### 3) 동영상 인물 자동 구분 포함
```bash
python transcribe_draft.py ./sample.mp4 -o ./sample_draft.txt --enable-video-person --hf-token YOUR_HF_TOKEN
```

## 출력 형식
음성 파일:
```text
[0001.23 - 0004.56] SPEAKER_00: 안녕하세요. 오늘 회의 시작하겠습니다.
```

동영상 + 인물 구분 사용 시:
```text
[0001.23 - 0004.56] SPEAKER_00 | PERSON_01: 안녕하세요. 오늘 회의 시작하겠습니다.
```

## 정확도 관련 안내
- `SPEAKER_XX`는 음성 기반 추정입니다.
- `PERSON_XX`는 영상 프레임의 얼굴 기반 추정입니다.
- 두 라벨은 초안 단계 자동 매핑이므로, 최종본에는 수동 검수 권장.
