from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.environ["NVIDIA_API_KEY"],
    base_url=os.environ["NVIDIA_BASE_URL"],
    timeout=30,
    max_retries=0,
)

try:
    response = client.chat.completions.create(
        model=os.environ["NEMOTRON_MODEL"],
        messages=[
            {"role": "system", "content": "Return strict JSON only."},
            {
                "role": "user",
                "content": 'Return exactly this JSON: {"claims": []}',
            },
        ],
        max_tokens=100,
        temperature=0,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )

    print("Model request: SUCCESS")
    print("Response:", repr(response.choices[0].message.content))

except Exception as exc:
    print("Model request: FAILED")
    print("Error type:", type(exc).__name__)
    print("Error:", str(exc))
