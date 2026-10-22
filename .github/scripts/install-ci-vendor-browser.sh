#!/usr/bin/env bash
set -euo pipefail

(($# == 1)) || exit 2
case "$1" in
  chrome|brave) MTG_BROWSER_VENDOR=$1 ;;
  *) exit 2 ;;
esac

# Preserve the native workflow's vendor-owned directory and repository checks.
test ! -L /opt
sudo -n install -d -o root -g root -m 0755 /opt
if [[ "$MTG_BROWSER_VENDOR" == chrome ]]; then
  test ! -L /opt/google
  test ! -L /opt/google/chrome
  sudo -n install -d -o root -g root -m 0755 /opt/google /opt/google/chrome
fi

if [[ "$MTG_BROWSER_VENDOR" == chrome ]]; then
  curl --connect-timeout 10 --max-time 90 -fsSLo "$RUNNER_TEMP/google-linux-key.pub" https://dl.google.com/linux/linux_signing_key.pub
  gpg --batch --show-keys --with-colons "$RUNNER_TEMP/google-linux-key.pub" | grep '^fpr:::::::::EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796:' >/dev/null
  gpg --batch --dearmor < "$RUNNER_TEMP/google-linux-key.pub" | sudo -n tee /usr/share/keyrings/mtg-google-chrome.gpg >/dev/null
  printf '%s\n' 'deb [arch=amd64 signed-by=/usr/share/keyrings/mtg-google-chrome.gpg,EB4C1BFD4F042F6DDDCCEC917721F63BD38B4796] https://dl.google.com/linux/chrome/deb/ stable main' | sudo -n tee /etc/apt/sources.list.d/mtg-google-chrome.list >/dev/null
  # Refresh only Google; retain the runner's Ubuntu indexes for dependencies.
  sudo -n /usr/bin/timeout --signal=TERM --kill-after=15s 120s apt-get \
    -o Dir::Etc::sourcelist=/etc/apt/sources.list.d/mtg-google-chrome.list \
    -o Dir::Etc::sourceparts=- -o APT::Get::List-Cleanup=0 \
    -o APT::Update::Error-Mode=any \
    -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 \
    -o Acquire::Retries=1 update
  sudo -n /usr/bin/timeout --signal=TERM --kill-after=15s 300s apt-get \
    -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 \
    -o Acquire::Retries=1 install -y --reinstall google-chrome-stable
else
  sudo -n curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg
  sudo -n curl -fsSLo /etc/apt/sources.list.d/brave-browser-release.sources https://brave-browser-apt-release.s3.brave.com/brave-browser.sources
  sudo -n apt-get update
  sudo -n apt-get install -y brave-browser
fi
