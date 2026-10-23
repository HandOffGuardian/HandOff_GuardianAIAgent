
import os
import json

from dotenv import load_dotenv
from openai import OpenAI


# --------------------------------------------------
# 1. Load environment variables from .env
# --------------------------------------------------

load_dotenv(override=True)

required_variables = [
    "NVIDIA_API_KEY",
    "NVIDIA_BASE_URL",
    "NEMOTRON_MODEL",
]

missing_variables = [
    variable
    for variable in required_variables
    if not os.getenv(variable)
]

if missing_variables:
    raise EnvironmentError(
        "Missing environment variables: "
        + ", ".join(missing_variables)
        + ". Check your .env file."
    )


# --------------------------------------------------
# 2. Initialize the NVIDIA Nemotron client
# --------------------------------------------------

client = OpenAI(
    api_key=os.environ["NVIDIA_API_KEY"],
    base_url=os.environ["NVIDIA_BASE_URL"],
)


# --------------------------------------------------
# 3. Define the sample text and extraction prompt
# --------------------------------------------------

sample_text = (
    "The customer says their payment of $250 "
    "was made on October 20, 2026."
)

system_prompt = """
You are a factual claim extraction assistant.

Extract factual claims explicitly stated in the supplied text.

Return only a valid JSON object with this structure:

{
  "claims": [
    {
      "claim_id": "C001",
      "field": "payment_amount",
      "claimed_value": "$250"
    }
  ]
}

Rules:
1. The top-level object must contain a "claims" array.
2. Each claim must contain claim_id, field, and claimed_value.
3. Assign unique claim IDs such as C001, C002, and C003.
4. Do not invent facts that are not stated in the text.
5. Use an empty claims array if no factual claims can be extracted.
6. Preserve the meaning of the original text.
7. Return JSON only, without Markdown fences or commentary.
"""


# --------------------------------------------------
# 4. Send the request to Nemotron
# --------------------------------------------------

try:
    response = client.chat.completions.create(
        model=os.environ["NEMOTRON_MODEL"],
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": f"Extract claims from this text:\n{sample_text}",
            },
        ],
        max_tokens=1024,
        temperature=0,
        extra_body={
            "chat_template_kwargs": {
                "enable_thinking": False
            }
        },
    )

    # --------------------------------------------------
    # 5. Read and display the response
    # --------------------------------------------------

    message = response.choices[0].message
    answer = message.content

    print("\n========== NEMOTRON RESPONSE ==========")
    print("Model:", response.model)
    print("Finish reason:", response.choices[0].finish_reason)
    print("Answer:")
    print(answer)

    # --------------------------------------------------
    # 6. Check whether the model returned an answer
    # --------------------------------------------------

    if response.choices[0].finish_reason == "length":
        print("\nWARNING: Generation reached the token limit.")

    if answer is None or not answer.strip():
        print("\nERROR: Nemotron returned no normal text answer.")
        raise RuntimeError(
            "No text answer returned. Check the model response "
            "and generation settings."
        )

    # --------------------------------------------------
    # 7. Parse and validate the JSON structure
    # --------------------------------------------------

    print("\n========== JSON VALIDATION ==========")

    try:
        data = json.loads(answer)
    except json.JSONDecodeError as exc:
        print("JSON validation: FAILED")
        print("Reason:", exc)
        raise

    if not isinstance(data, dict):
        raise ValueError("The response must be a JSON object.")

    claims = data.get("claims")

    if not isinstance(claims, list):
        raise ValueError("'claims' must be a JSON array.")

    required_claim_fields = {
        "claim_id",
        "field",
        "claimed_value",
    }

    for index, claim in enumerate(claims, start=1):
        if not isinstance(claim, dict):
            raise ValueError(
                f"Claim {index} must be a JSON object."
            )

        missing_fields = required_claim_fields - claim.keys()

        if missing_fields:
            raise ValueError(
                f"Claim {index} is missing fields: "
                + ", ".join(sorted(missing_fields))
            )

        for field in required_claim_fields:
            value = claim[field]

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"Claim {index} has an invalid '{field}' value."
                )

    claim_ids = [claim["claim_id"] for claim in claims]

    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("Claim IDs must be unique.")

    print("JSON validation: PASSED")
    print("Number of claims:", len(claims))

    print("\n========== EXTRACTED CLAIMS ==========")

    for claim in claims:
        print(f"ID: {claim['claim_id']}")
        print(f"Field: {claim['field']}")
        print(f"Value: {claim['claimed_value']}")
        print("-" * 35)

except Exception as exc:
    print("\nNemotron test failed.")
    print("Error type:", type(exc).__name__)
    print("Error:", str(exc))
    raise
