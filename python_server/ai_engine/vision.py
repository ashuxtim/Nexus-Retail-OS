# FILE: python_server/ai_engine/vision.py

import json
import base64
import io
from PIL import Image
from groq import Groq


async def scan_receipt_engine(file_bytes, api_key=None):
    """
    Analyzes a receipt image using the provided API Key.
    """
    try:
        # 1. Validate Key
        if not api_key:
            return {
                "supplier": {"name": "Config Error", "mobile": "", "address": ""},
                "items": [
                    {
                        "product_name": "Groq API Key Missing",
                        "quantity": 0,
                        "unit_price": 0,
                        "total_cost": 0,
                    }
                ],
                "error_log": "API Key was None",
            }

        # 2. Image Pre-processing
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        client = Groq(api_key=api_key)

        # 3. Vision Request
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract data from this receipt in strict JSON format. Keys: supplier (object with name, mobile, address), items (list of objects with product_name, quantity, unit_price, total_cost), total_amount, date. Do not include markdown formatting like ```json ... ```.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{img_str}",
                            },
                        },
                    ],
                }
            ],
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            temperature=0,
            max_tokens=1024,
        )

        # 4. Clean Response
        response_content = chat_completion.choices[0].message.content

        if "```json" in response_content:
            response_content = (
                response_content.split("```json")[1].split("```")[0].strip()
            )
        elif "```" in response_content:
            response_content = response_content.split("```")[1].split("```")[0].strip()

        return json.loads(response_content)

    except Exception as e:
        return {
            "supplier": {"name": "Scan Failed", "mobile": "", "address": ""},
            "items": [
                {
                    "product_name": "Error scanning receipt",
                    "quantity": 1,
                    "unit_price": 0,
                    "total_cost": 0,
                }
            ],
            "error_log": str(e),
        }
