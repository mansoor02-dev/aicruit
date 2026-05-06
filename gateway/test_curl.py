import urllib.request
import urllib.error

data = b'{"resume_id":"deb935bb-754a-4462-a3ff-fc19a8b2a912"}'
req = urllib.request.Request('http://localhost:8006/parse-resume', data=data, headers={'Content-Type': 'application/json'})
try:
    response = urllib.request.urlopen(req)
    print(response.read())
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code} - {e.read()}")
except Exception as e:
    print(f"Error: {e}")
