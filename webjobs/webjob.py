import requests
import datetime

API_URL = "https://kdev-real-estate-api.azurewebsites.net/api/v1/real-estate/create"


def main():
    now = datetime.datetime.now()
    print(f"[{now}] Calling {API_URL}")

    try:
        response = requests.post(API_URL, headers={"Accept": "application/json"})
        print(f"Status code: {response.status_code}")
        print("Response:", response.text)
    except Exception as e:
        print("Error while calling API:", e)


if __name__ == "__main__":
    main()
