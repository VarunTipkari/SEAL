import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


load_dotenv()


MODEL = os.getenv(
    "MODEL",
    "gpt-5.4-mini"
)


llm = ChatOpenAI(
    model=MODEL,
    temperature=0
)