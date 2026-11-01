@echo off
title TRUTHMAP AI — Easy GitHub Upload
echo ========================================================
echo        TRUTHMAP AI — One-Click GitHub Uploader
echo ========================================================
echo.

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Git is not installed or not in your PATH.
    echo Please install Git from https://git-scm.com/ and try again.
    pause
    exit /b 1
)

echo [1/4] Checking Git repository status...
if not exist ".git" (
    echo Initializing local git repository on branch main...
    git init -b main
)

echo [2/4] Staging files (protecting .env and local databases via .gitignore)...
git add .

git status --short
echo.

set /p COMMIT_MSG="Enter commit message (Press Enter for default 'feat: update TRUTHMAP AI platform'): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=feat: update TRUTHMAP AI platform

git commit -m "%COMMIT_MSG%" 2>nul
if %errorlevel% equ 0 (
    echo [OK] Changes committed successfully.
) else (
    echo [INFO] No new changes to commit or commit already up to date.
)

echo.
echo [3/4] Checking remote origin...
git remote get-url origin >nul 2>nul
if %errorlevel% equ 0 (
    echo Current remote origin:
    git remote get-url origin
    echo.
    set /p CHANGE_REMOTE="Do you want to change the remote URL? (y/N): "
    if /i "%CHANGE_REMOTE%"=="y" (
        set /p NEW_URL="Enter new GitHub repository URL: "
        git remote set-url origin %NEW_URL%
    )
) else (
    echo No remote origin configured.
    echo.
    echo Please create an empty repository on GitHub: https://github.com/new
    echo Name: truthmap-ai (Leave all checkboxes UNCHECKED)
    echo.
    set /p REPO_URL="Enter your GitHub repository URL (e.g., https://github.com/username/truthmap-ai.git): "
    if not "%REPO_URL%"=="" (
        git remote add origin %REPO_URL%
    ) else (
        echo [ERROR] No URL provided. Aborting.
        pause
        exit /b 1
    )
)

echo.
echo [4/4] Pushing branch 'main' to GitHub...
git branch -M main
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo  SUCCESS! Your TRUTHMAP AI repository is live on GitHub!
    echo ========================================================
) else (
    echo.
    echo [NOTICE] Push failed or authentication needed.
    echo If this is your first time pushing to GitHub:
    echo 1. Ensure you have created the repository on https://github.com/new
    echo 2. Check your credentials (use a Personal Access Token if prompted).
    echo 3. Or push via SSH if your SSH keys are configured.
)

echo.
pause
