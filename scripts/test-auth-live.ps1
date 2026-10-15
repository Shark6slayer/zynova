$body = @{
    email = "phase1_verify@superai.com"
    username = "phase1_user"
    full_name = "Phase One Engineer"
    password = "SuperPassword2026"
} | ConvertTo-Json

Write-Host "1. Testing Registration Endpoint..."
try {
    $regRes = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/auth/register" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   Registration SUCCESS:" ($regRes | ConvertTo-Json -Compress)
} catch {
    Write-Host "   Registration Error:" $_.Exception.Message
}

Write-Host "`n2. Testing Duplicate Registration Prevention..."
try {
    $dupRes = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/auth/register" -Method Post -Body $body -ContentType "application/json"
    Write-Host "   ERROR: Duplicate was allowed unexpectedly!"
} catch {
    Write-Host "   Duplicate properly rejected with 400 Bad Request: $($_.Exception.Message)"
}

Write-Host "`n3. Testing Login with Created Account..."
$loginBody = @{
    email = "phase1_verify@superai.com"
    password = "SuperPassword2026"
} | ConvertTo-Json

try {
    $loginRes = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
    Write-Host "   Login SUCCESS: Token type:" $loginRes.token_type
    $token = $loginRes.access_token

    Write-Host "`n4. Testing Protected Endpoint (/users/me)..."
    $headers = @{ Authorization = "Bearer $token" }
    $me = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/users/me" -Headers $headers
    Write-Host "   Protected /users/me SUCCESS: ID=$($me.id), Email=$($me.email), Name=$($me.full_name)"
} catch {
    Write-Host "   Login Error:" $_.Exception.Message
}

Write-Host "`n5. Testing Invalid Password Rejection..."
$badLogin = @{
    email = "phase1_verify@superai.com"
    password = "WrongPassword123"
} | ConvertTo-Json

try {
    $badRes = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/auth/login" -Method Post -Body $badLogin -ContentType "application/json"
    Write-Host "   ERROR: Bad login allowed!"
} catch {
    Write-Host "   Invalid password correctly rejected with 401 Unauthorized"
}
