# Recording

음성 파일(.wav, .mp3 등)과 동영상 파일(.mp4 등)을 **전사하고 화자별로 나누는 초안**을 빠르게 만들기 위한 스타터입니다.

## 포함된 파일
- `transcribe_draft.py`: 전사 + (선택) 화자 분리 + 초안 텍스트 출력

## 빠른 시작
```bash
pip install whisperx
python transcribe_draft.py ./sample.mp4 -o ./sample_draft.txt --device cpu --compute-type int8
```

GPU 사용 시 예시:
```bash
python transcribe_draft.py ./sample.wav -o ./sample_draft.txt --device cuda --compute-type float16
```

화자 분리(다이어라이제이션)까지 하려면 Hugging Face 토큰을 전달하세요.
```bash
python transcribe_draft.py ./sample.wav -o ./sample_draft.txt --hf-token YOUR_HF_TOKEN
```

## 출력 형식(초안)
```text
[0001.23 - 0004.56] SPEAKER_00: 안녕하세요. 오늘 회의 시작하겠습니다.
[0004.80 - 0008.10] SPEAKER_01: 네, 자료 공유드렸습니다.
```

## 권장 후처리
- 고유명사/숫자 표기 교정
- SPEAKER 태그를 실제 이름으로 매핑
- 문장부호 및 줄바꿈 정리
