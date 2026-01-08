import traceback
import os
from backend.config import settings

print('GEMINI_API_KEY present:', bool(os.getenv('GEMINI_API_KEY')))
print('GEMINI_API_KEY (first 8 chars):', (os.getenv('GEMINI_API_KEY') or '')[:8])

try:
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    print('Imported langchain_google_genai OK')
except Exception as e:
    print('Import error for langchain_google_genai:', e)
    traceback.print_exc()
    raise

# Quick embeddings test
try:
    emb = GoogleGenerativeAIEmbeddings(model='models/embedding-001', google_api_key=settings.GEMINI_API_KEY)
    vec = emb.embed_query('test')
    print('Embedding OK, vector length:', len(vec))
except Exception as e:
    print('Embedding call failed:', e)
    traceback.print_exc()

# Quick chat test
try:
    llm = ChatGoogleGenerativeAI(model='gemini-2.5-flash', google_api_key=settings.GEMINI_API_KEY, temperature=0)
    messages = [{"role": "system", "content": "You are a test."}, {"role": "user", "content": "Say hello."}]
    resp = llm.invoke(messages)
    print('LLM response type:', type(resp))
    print('LLM response:', getattr(resp, 'content', resp))
except Exception as e:
    print('LLM call failed:', e)
    traceback.print_exc()
