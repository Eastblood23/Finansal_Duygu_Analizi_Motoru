"""Manual opt-in provider check. --generate makes one potentially billable request."""
import argparse
import asyncio

from google import genai
from google.genai import errors, types
from app.config import settings


async def check(generate=False, list_models=False):
    secret = settings.gemini_api_key.get_secret_value().strip() if settings.gemini_api_key else ""
    if not secret or secret == "your_gemini_api_key_here":
        print("SKIPPED: Gemini API key is not configured")
        return
    try:
        async with genai.Client(
            api_key=secret,
            http_options=types.HttpOptions(
                timeout=settings.gemini_timeout_seconds * 1000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        ).aio as client:
            if list_models:
                async for model in await client.models.list():
                    if "flash" in (model.name or "") and "generateContent" in (model.supported_actions or []):
                        print("Available text model:", model.name)
                return
            if generate:
                response = await client.models.generate_content(
                    model=settings.gemini_model,
                    contents="Yalnızca OK yaz.",
                    config=types.GenerateContentConfig(max_output_tokens=settings.gemini_max_output_tokens),
                )
                if not response.text or not response.text.strip():
                    raise RuntimeError("Empty response")
                print("Single synthetic generation: PASS")
            else:
                await client.models.get(model=settings.gemini_model)
                print("Model metadata access: PASS")
    except errors.APIError as error:
        print("Provider check failed; HTTP status:", error.code)
        raise SystemExit(1) from None
    except Exception as error:
        print("Provider check failed; type:", type(error).__name__)
        raise SystemExit(1) from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true")
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args()
    asyncio.run(check(args.generate, args.list_models))
