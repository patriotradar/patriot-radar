# ffuf-scanner

Standalone [ffuf](https://github.com/ffuf/ffuf) v2.2.1 setup — kept separate from the tiktok-dashboard (creator radar).

## Install

```bash
cd ffuf-scanner
bash setup.sh
```

This downloads the official `ffuf_2.2.1_linux_amd64.tar.gz` release, verifies its SHA-256 checksum, and places the binary at `ffuf-scanner/bin/ffuf`.

## Requirements

- `curl`
- `sha256sum` (part of `coreutils` on Linux; `brew install coreutils` on macOS)
- `tar`

## Basic usage

```bash
# Directory/path fuzzing
./bin/ffuf -u https://example.com/FUZZ -w /path/to/wordlist.txt

# Subdomain fuzzing
./bin/ffuf -u https://FUZZ.example.com -w /path/to/subdomains.txt -H "Host: FUZZ.example.com"

# POST body fuzzing
./bin/ffuf -u https://example.com/login -X POST \
  -d "username=admin&******" \
  -w /path/to/passwords.txt \
  -H "Content-Type: application/x-www-form-urlencoded"

# Output results to a file
./bin/ffuf -u https://example.com/FUZZ -w /path/to/wordlist.txt -o results.json -of json
```

## GitHub Actions

A workflow at `.github/workflows/ffuf-install.yml` can install and run ffuf in CI independently of the creator-radar workflows. Trigger it manually from the **Actions** tab.

## Notes

- The `bin/` directory and all output files (`.txt`, `.json`, `.csv`, `.html`) are git-ignored.
- Only `setup.sh`, `README.md`, and `.gitignore` are tracked in version control.
- To update the version, change `FFUF_VERSION` at the top of `setup.sh` and update this README.
