#!/bin/bash

TOKEN="g5XLmE5AxpHQF4u4yADXZFHNgfrOtXQst9UQMqqOxqw"
URL="https://karaapp.onrender.com/api/v1/records"

curl -s -w "\nHTTP STATUS: %{http_code}\n" \
  -H "Authorization: Bearer $TOKEN" \
  "$URL"
