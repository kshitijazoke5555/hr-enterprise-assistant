import requests
import os

API = 'http://127.0.0.1:8000'

s = requests.Session()
# Use email form so frontend validation passes
login_payload = {
    'username': 'hr_bob@example.com',
    'password': 'hrpass',
    'role': 'HR',
    'department': 'hr',
    'country': 'india'
}
print('Logging in...')
resp = s.post(f'{API}/login', json=login_payload)
print('Login status:', resp.status_code, resp.text)

query_payload = {'question': 'What is the sick leave policy?'}
print('Querying...')
resp2 = s.post(f'{API}/query', json=query_payload)
print('Query status:', resp2.status_code)
try:
    print('Query response json:', resp2.json())
except Exception as e:
    print('Response text:', resp2.text)
    print('Error parsing json:', e)
