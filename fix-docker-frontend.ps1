# Frontend-Image entfernen und neu bauen (behebt I/O-Fehler bei Docker)
$imageName = "ai-based-web-exam-simulation-with-automated-identity-verification-frontend"

Write-Host "1. Altes Frontend-Image entfernen (mit -f)..."
docker rmi ${imageName}:latest -f 2>$null
docker rmi ${imageName} -f 2>$null

Write-Host "2. Ungenutzte Docker-Daten bereinigen (behebt defekte Blobs)..."
docker builder prune -f
docker image prune -f

Write-Host "3. Nur Frontend neu bauen (ohne Cache, mit Ausgabe)..."
docker compose build frontend --no-cache --progress=plain

if ($LASTEXITCODE -eq 0) {
    Write-Host "4. Container starten..."
    docker compose up
} else {
    Write-Host "Build fehlgeschlagen. Siehe Fehlermeldung oben."
}
