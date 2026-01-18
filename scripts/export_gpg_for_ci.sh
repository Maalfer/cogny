#!/bin/bash

# Configuration
KEY_NAME="cogny"

echo "=== GPG Key Export Helper for GitHub Actions ==="
echo "This script will help you export your GPG private key formatted for GitHub Secrets."
echo ""

# Check for GPG
if ! command -v gpg &> /dev/null; then
    echo "Error: gpg could not be found."
    exit 1
fi

# List keys to help user identify
echo "Available Secret Keys:"
gpg --list-secret-keys --keyid-format LONG
echo ""

# Ask for Key ID if not provided as argument
if [ -z "$1" ]; then
    read -p "Enter the Key ID you want to export (e.g., from the sec line above, without 'sec' prefix): " KEY_ID
else
    KEY_ID="$1"
fi

if [ -z "$KEY_ID" ]; then
    echo "Error: No Key ID provided."
    exit 1
fi

echo ""
echo "Exporting key ${KEY_ID}..."
echo ""

# Export to a temporary file
gpg --export-secret-keys --armor "$KEY_ID" > private_key.asc

if [ ! -s private_key.asc ]; then
    echo "Error: Failed to export key. Please check the Key ID and try again."
    rm -f private_key.asc
    exit 1
fi

echo "----------------------------------------------------------------"
echo "COPY THE CONTENT BELOW TO YOUR GITHUB SECRET 'GPG_PRIVATE_KEY':"
echo "----------------------------------------------------------------"
cat private_key.asc
echo "----------------------------------------------------------------"

# Clean up
rm private_key.asc

echo ""
echo "Done. Remember to also set 'GPG_PASSPHRASE' if your key is protected."
