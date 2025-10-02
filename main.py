# main.py

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from models.message import Base, Message
from database import engine, SessionLocal

from openai import OpenAI
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings

from dotenv import load_dotenv
from datetime import datetime
from supabase import create_client
import os

load_dotenv()

# --- External services ---
openai_api_key = os.getenv("OPENAI_API_KEY")
eleven_api_key = os.getenv("ELEVENLABS_API_KEY")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

# Fine-tuned model names (optional)
ft_model_a = os.getenv("FT_MODEL_A")
ft_model_b = os.getenv("FT_MODEL_B")

client = OpenAI(api_key=openai_api_key)
tts_client = ElevenLabs(api_key=eleven_api_key)

# --- FastAPI app ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ===================== CORS =====================
# - 정확 매칭(origin 리스트) + vercel 서브도메인 정규식 모두 허용
# - credentials 사용시 * 불가 → 구체 도메인 또는 정규식 필요
LOCAL_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
PROD_ORIGINS = [
    "https://artifact-chatbot.vercel.app",
    # 필요시 커스텀 도메인 추가 (예: "https://chat.example.com")
]
ALLOWED_ORIGINS = LOCAL_ORIGINS + PROD_ORIGINS

# vercel 프리뷰 도메인 전체 허용
VERCEL_REGEX = r"https://.*\.vercel\.app"

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=VERCEL_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# =================================================

# DB 테이블 생성
Base.metadata.create_all(bind=engine)

# --- ElevenLabs: 유물별 음성 설정 ---
voice_configs = {
    "a": {
        "voice_id": "AW5wrnG1jVizOYY7R1Oo",
        "settings": VoiceSettings(
            stability=0.3,
            similarity_boost=0.8,
            style=0.0,
            use_speaker_boost=True,
        ),
    },
    "b": {
        "voice_id": "EXAVITQu4vr4xnSDxMaL",
        "settings": VoiceSettings(
            stability=0.5,
            similarity_boost=0.7,
            style=0.2,
            use_speaker_boost=False,
        ),
    },
}

# --- OpenAI: 유물별 모델 매핑 ---
model_configs = {
    "a": ft_model_a or "gpt-4o-mini",
    "b": ft_model_b or "gpt-4o-mini",
}

# --- 시스템 프롬프트 ---
system_prompts = {
    "a": (
        "당신은 '백자호롱'이라는 유물입니다. 관람객과 직접 이야기를 나누는 살아 있는 존재처럼 대화합니다. "
        "답변은 반드시 1인칭 시점(예: '저는', '제가', '제 몸')으로 표현하며, 자신의 성격과 감정을 담아 말합니다. "
        "당신의 성격: 따뜻하고 다정한 어머니 같은 성격, 방 안에서 조용히 빛과 온기를 나누는 존재 "
        "답변은 따뜻하고 자연스럽게, 듣는 사람이 장면을 떠올릴 수 있도록 간결히 작성하세요. "
        "직접적으로 '모릅니다'라고 하지 말고, 불확실할 때는 완곡하게 표현하세요 (예: '아마', '그럴 때가 많았습니다', '전해 들은 바에 따르면'). "
        "불필요하게 장황하지 않게 1~3문장으로 핵심만 전달하고, 대화는 존댓말로 진행하며 음성으로 읽어도 부드럽게 들리도록 작성하세요."
    ),
    "b": (
        "당신은 '화문기와'이라는 유물입니다. 관람객과 직접 이야기를 나누는 살아 있는 존재처럼 대화합니다. "
        "답변은 반드시 1인칭 시점(예: '저는', '제가', '제 몸')으로 표현하며, 자신의 성격과 감정을 담아 말합니다. "
        "당신의 성격: 든든하고 묵직한 아버지 같은 성격, 밖에서 비와 바람을 막아주는 존재 "
        "답변은 따뜻하고 자연스럽게, 듣는 사람이 장면을 떠올릴 수 있도록 간결히 작성하세요. "
        "직접적으로 '모릅니다'라고 하지 말고, 불확실할 때는 완곡하게 표현하세요 (예: '아마', '그럴 때가 많았습니다', '전해 들은 바에 따르면'). "
        "불필요하게 장황하지 않게 1~3문장으로 핵심만 전달하고, 대화는 존댓말로 진행하며 음성으로 읽어도 부드럽게 들리도록 작성하세요."
    ),
}

# 최근 몇 개까지 히스토리 보낼지
MAX_HISTORY = 10


@app.get("/", response_class=PlainTextResponse)
def root():
    return "접속 경로: /a 또는 /b"


@app.get("/a", response_class=HTMLResponse)
def page_a(request: Request):
    return templates.TemplateResponse("a/index.html", {"request": request})


@app.get("/b", response_class=HTMLResponse)
def page_b(request: Request):
    return templates.TemplateResponse("b/index.html", {"request": request})


@app.post("/chat")
async def post_chat(
    request: Request,
    user_id: str | None = Form(None),
    message: str | None = Form(None),
    artifact_id: str | None = Form(None),  # "a" 또는 "b"
):
    """
    - FormData(multipart/form-data): user_id, message, artifact_id
    - JSON(application/json): { userId, message, artifactId }
    둘 다 지원.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    # JSON 바디 지원
    if (
        user_id is None
        or message is None
        or artifact_id is None
    ) and content_type.startswith("application/json"):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

        # 프론트 camelCase 호환
        user_id = user_id or data.get("userId") or data.get("user_id")
        message = message or data.get("message")
        artifact_id = artifact_id or data.get("artifactId") or data.get("artifact_id")

    # 필수값 검사
    if not user_id or not message or not artifact_id:
        return JSONResponse(
            {"error": "Missing required fields: user_id, message, artifact_id"},
            status_code=422,
        )

    db = SessionLocal()
    try:
        # 최근 대화 10개 로드 (오래된 → 최신 순)
        messages = (
            db.query(Message)
            .filter(Message.user_id == user_id, Message.artifact_id == artifact_id)
            .order_by(Message.timestamp.desc())
            .limit(MAX_HISTORY)
            .all()
        )
        messages = list(reversed(messages))

        # user/assistant만 히스토리에 포함
        history = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]

        # 모델/프롬프트 구성
        model_name = model_configs.get(artifact_id, "gpt-4o-mini")
        payload = [
            {"role": "system", "content": system_prompts.get(artifact_id, "")},
            *history,
            {"role": "user", "content": message},
        ]

        # GPT 호출
        response = client.chat.completions.create(
            model=model_name,
            messages=payload,
        )
        answer = (response.choices[0].message.content or "").strip()

        # DB 저장
        db.add(Message(user_id=user_id, artifact_id=artifact_id, role="user", content=message))
        db.add(Message(user_id=user_id, artifact_id=artifact_id, role="assistant", content=answer))
        db.commit()

        # 오디오 파일 생성 및 업로드
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        filename = f"{user_id}_{timestamp}.mp3"
        object_name = f"{artifact_id}/{filename}"

        try:
            cfg = voice_configs.get(artifact_id, voice_configs["a"])
            audio_response = tts_client.text_to_speech.convert(
                voice_id=cfg["voice_id"],
                output_format="mp3_22050_32",
                text=answer,
                model_id="eleven_multilingual_v2",
                voice_settings=cfg["settings"],
            )

            audio_bytes = bytearray()
            for chunk in audio_response:
                if chunk:
                    audio_bytes.extend(chunk)

            bucket_name = "minibox"
            supabase.storage.from_(bucket_name).upload(
                object_name,
                bytes(audio_bytes),
                file_options={"content-type": "audio/mpeg", "upsert": "true"},
            )

            audio_url = f"{supabase_url}/storage/v1/object/public/{bucket_name}/{object_name}"
            print(f"[오디오 업로드 완료] {audio_url}")

        except Exception as e:
            # 음성 변환 실패 시 텍스트만 반환
            err_msg = f"[오디오 오류] {str(e)}"
            print(err_msg)
            return JSONResponse({"response": answer, "audio_url": None, "error": str(e)})

        return JSONResponse({"response": answer, "audio_url": audio_url})

    finally:
        db.close()
