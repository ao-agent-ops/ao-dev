import os
from google import genai
from google.genai import types


def main():
    if "GOOGLE_API_KEY" in os.environ:
        del os.environ["GOOGLE_API_KEY"]

    # Create a Vertex AI client using default credentials
    client = genai.Client()

    response = client.models.generate_content(
        model='gemini-2.5-flash-image',
        contents='A cartoon infographic for flying sneakers',
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="9:16",
            ),
        ),
    )
    print(response)


if __name__ == "__main__":
    main()