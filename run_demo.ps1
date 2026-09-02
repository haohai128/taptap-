$env:OPENAI_BASE_URL = "http://localhost:11434/v1"
$env:OPENAI_API_KEY  = "dummy"
$env:OPENAI_MODEL    = "dummy"
Set-Location "C:\Users\libenhao\community-sentiment"
py -m app serve
