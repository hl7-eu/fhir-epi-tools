import os
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq
from ollama import Client
from openai import OpenAI

load_dotenv()

SERVER_URL = os.getenv("SERVER_URL")
MODEL_URL = os.getenv("MODEL_URL")
OPENAIKEY = os.getenv("OPENAI_KEY")
GROQAPIKEY = os.getenv("GROQ_API_KEY")

print(MODEL_URL)
if MODEL_URL is not None:
    client = Client(host=MODEL_URL)

if OPENAIKEY is not None:
    openaiclient = OpenAI(
        # This is the default and can be omitted
        api_key=OPENAIKEY
    )
if GROQAPIKEY is not None:
    groqclient = Groq(api_key=GROQAPIKEY)

LANGUAGE_MAP = {
    "es": "Spanish",
    "en": "English",
    "de": "German",
    "fr": "French",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "tr": "Turkish",
    "ar": "Arabic",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "vi": "Vietnamese",
    "th": "Thai",
    "el": "Greek",
    "cs": "Czech",
    "hu": "Hungarian",
    "ro": "Romanian",
    "sv": "Swedish",
    "fi": "Finnish",
    "da": "Danish",
    "no": "Norwegian",
    "is": "Icelandic",
    "et": "Estonian",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "mt": "Maltese",
    "hr": "Croatian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "bg": "Bulgarian",
    "cy": "Welsh",
    "ga": "Irish",
    "gd": "Gaelic",
    "eu": "Basque",
    "ca": "Catalan",
    "gl": "Galician",
}


def parse_response_split(response):
    nresp = []
    for r in response.split("|"):
        if r.strip() != "":
            nresp.append(r.strip())

    return nresp


def explaining_plain_language(language, data_to_explain, model):
    lang = LANGUAGE_MAP[language]

    piped_sentences = "|".join(data_to_explain)
    prompt = f"Please simplify the following technical health information into plain language suitable for a patient with no health literacy. Each piece of information is separated by '|'. Provide the simplified explanation for each piece of information in the same order, using the same delimiter '|'. Ensure the explanations are clear, concise, and easy to understand.\n\nOriginal: {piped_sentences}\nAnswer:"
    if "llama3" in model:
        systemMessage = (
            """You are an AI assistant specialized in simplifying technical health information for different age groups. Your task is to read complex medical sentences separated by a delimiter and rewrite them in simple language appropriate for the specified age. Each piece of information is separated by a '|' character. Maintain the structure and format in your response, ensuring each simplified sentence is also separated by '|'.\n
        You must follow this indications extremety strictly:\n
        1. You must answer in """
            + lang
            + """ \n

        """
        )

        print("prompt is:" + prompt)

        prompt_message = prompt
        result = client.chat(
            model="llama3",
            messages=[
                {"content": systemMessage, "role": "system"},
                {"content": prompt_message, "role": "assistant"},
            ],
            stream=False,
            keep_alive="-1m",
        )

        response = result["message"]["content"]
        print(response)
        # print(response.split("|"))

        parsed_response = parse_response_split(response)
        if len(parsed_response) != len(data_to_explain):
            errormessage = (
                "Error: The number of responses does not match the number of inputs",
                len(parsed_response),
                len(data_to_explain),
            )
            raise Exception(errormessage)
    return {
        "response": parsed_response,
        "prompt": prompt,
        "datetime": datetime.now(),
        "model": model,
    }
