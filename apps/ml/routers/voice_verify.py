from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import whisper
import tempfile
import os

router = APIRouter(prefix="/voice", tags=["Voice Verification"])

# Load Whisper model once at startup (use "base" for low-resource, "medium" for better accuracy)
whisper_model = whisper.load_model("base")

# Supported Indian scripts for rendering
LANGUAGE_SCRIPT_MAP = {
    "hi": "Devanagari",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "bn": "Bengali",
    "gu": "Gujarati",
    "mr": "Marathi",
    "pa": "Gurmukhi",
    "or": "Odia",
    "ur": "Nastaliq",
    "en": "Latin",
}


@router.post("/verify")
async def verify_medicine_voice(audio: UploadFile = File(...)):
    """
    Accepts an audio file, transcribes it with Whisper ASR,
    detects language, and verifies the medicine via LangChain + CDSCO.
    """
    # Validate file type
    if audio.content_type not in ["audio/webm", "audio/wav", "audio/ogg", "audio/mp4", "audio/mpeg"]:
        raise HTTPException(status_code=400, detail="Unsupported audio format. Use webm, wav, ogg, or mp4.")

    # Save to temp file for Whisper
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name

    try:
        # Transcribe with Whisper (auto-detects language)
        result = whisper_model.transcribe(tmp_path, task="transcribe")
        transcribed_text = result.get("text", "").strip()
        detected_lang = result.get("language", "en")

        if not transcribed_text:
            raise HTTPException(status_code=422, detail="Could not transcribe audio. Please speak clearly.")

        # Get script name for detected language
        script = LANGUAGE_SCRIPT_MAP.get(detected_lang, "Latin")

        # Use LangChain to verify medicine against CDSCO (mocked — replace with real DB/API call)
        # In production: query your Supabase CDSCO table here instead
        verification_result = await verify_with_cdsco(transcribed_text, detected_lang, script)

        return JSONResponse(content={
            "success": True,
            "transcribed": transcribed_text,
            "detected_language": detected_lang,
            "script": script,
            "verification": verification_result,
        })

    finally:
        os.unlink(tmp_path)  # Clean up temp file


async def verify_with_cdsco(medicine_name: str, language: str, script: str) -> dict:
    """
    Verifies medicine name against CDSCO database.
    TODO: Replace mock with actual Supabase query.
    """
    # --- MOCK RESPONSE (replace with real DB query) ---
    # In production, query: SELECT * FROM medicines WHERE name ILIKE %medicine_name%
    mock_db = {
        "paracetamol": {
            "status": "verified",
            "manufacturer": "Cipla Ltd.",
            "category": "Analgesic / Antipyretic",
            "cdsco_registered": True,
            "warnings": [],
        },
        "crocin": {
            "status": "verified",
            "manufacturer": "GSK Consumer Healthcare",
            "category": "Analgesic / Antipyretic",
            "cdsco_registered": True,
            "warnings": ["Do not exceed 4g/day"],
        },
    }

    name_lower = medicine_name.lower()
    match = next((v for k, v in mock_db.items() if k in name_lower), None)

    if match:
        return {
            "medicine_name_original": medicine_name,
            "medicine_name_english": medicine_name,
            "medicine_name_regional": medicine_name,  # TODO: translate via Sarvam AI
            "detected_language": language,
            "script": script,
            **match,
        }

    return {
        "medicine_name_original": medicine_name,
        "medicine_name_english": medicine_name,
        "medicine_name_regional": medicine_name,
        "status": "not_found",
        "manufacturer": "Unknown",
        "category": "Unknown",
        "cdsco_registered": False,
        "warnings": ["Medicine not found in CDSCO database. Consult a pharmacist."],
        "detected_language": language,
        "script": script,
    }


@router.get("/languages")
async def get_supported_languages():
    """Returns list of supported Indian languages and their scripts."""
    return {"supported_languages": LANGUAGE_SCRIPT_MAP}
