$ErrorActionPreference = "Stop"

Remove-Item -Recurse -Force build, ingest.zip -ErrorAction SilentlyContinue

pip install --no-deps entsoe-py -t build
pip install requests beautifulsoup4 pytz -t build `
  --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all:

Copy-Item src\*.py build\
Remove-Item -Recurse -Force build\bin, build\__pycache__ -ErrorAction SilentlyContinue

Compress-Archive -Path build\* -DestinationPath ingest.zip -Force
"{0:N2} MB" -f ((Get-Item ingest.zip).Length / 1MB)
