#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

set -e

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}        Git Professional Agent           ${NC}"
echo -e "${BLUE}=========================================${NC}\n"

current_branch=$(git branch --show-current)
read -p "Confirm or create new branch [Current: $current_branch]: " branch_input
branch_name=${branch_input:-$current_branch}

if [ "$branch_name" != "$current_branch" ]; then
    git checkout -b "$branch_name" 2>/dev/null || git checkout "$branch_name"
fi

echo -e "\n${YELLOW}Analyzing changes...${NC}"
git add .
status_changes=$(git diff --cached --name-status)

if [ -z "$status_changes" ]; then
    echo "No changes detected to commit. Exiting."
    exit 0
fi

echo -e "\n${GREEN}Files modified:${NC}"
echo "$status_changes"

echo -e "\n${BLUE}Quality Gates (required):${NC}"
read -p "Test command [default: pytest]: " test_cmd
test_cmd=${test_cmd:-pytest}
echo -e "${YELLOW}Running tests...${NC}"
bash -lc "$test_cmd"

read -p "Lint command [default: python -m ruff check .]: " lint_cmd
lint_cmd=${lint_cmd:-python -m ruff check .}
echo -e "${YELLOW}Running lint...${NC}"
bash -lc "$lint_cmd"

read -p "Build command [default: python -m compileall Src]: " build_cmd
build_cmd=${build_cmd:-python -m compileall Src}
echo -e "${YELLOW}Running build...${NC}"
bash -lc "$build_cmd"

echo -e "\n${BLUE}Select the Commit Type:${NC}"
select commit_type in "feat (New feature)" "fix (Bug fix)" "refactor (Code change)" "docs (Documentation)" "chore (Maintenance/Dependencies)"; do
    case $commit_type in
        "feat "*) type="feat"; break ;;
        "fix "*) type="fix"; break ;;
        "refactor "*) type="refactor"; break ;;
        "docs "*) type="docs"; break ;;
        "chore "*) type="chore"; break ;;
        *) echo "Invalid option. Try again." ;;
    esac
done

while true; do
    read -p "Scope (required, lowercase, e.g. sr, cgf, pmpv-ui): " commit_scope
    if [[ "$commit_scope" =~ ^[a-z0-9-]+$ ]]; then
        break
    fi
    echo "Invalid scope. Use lowercase letters, numbers, and hyphens only."
done

read -p "Breaking change? [y/N]: " breaking_input
breaking_input=$(echo "$breaking_input" | tr '[:upper:]' '[:lower:]')
is_breaking=false
if [ "$breaking_input" = "y" ] || [ "$breaking_input" = "yes" ]; then
    is_breaking=true
fi

echo -e "\n${YELLOW}What exactly did you do?${NC}"
while true; do
    read -p "Title (Professional English): " commit_title
    if [ -n "$commit_title" ]; then
        break
    fi
    echo "Title is required."
done

echo -e "\n${YELLOW}Describe the changes in detail:${NC}"
read -p "Body (Professional English, optional): " commit_body

if [ "$is_breaking" = true ]; then
    while true; do
        read -p "BREAKING CHANGE impact summary (required): " breaking_summary
        if [ -n "$breaking_summary" ]; then
            break
        fi
        echo "Impact summary is required for breaking changes."
    done
fi

commit_header="$type($commit_scope): $commit_title"
if [ "$is_breaking" = true ]; then
    commit_header="$type!($commit_scope): $commit_title"
fi

if [ -z "$commit_body" ]; then
    final_message="$commit_header"
else
    final_message="$commit_header\n\n$commit_body"
fi

if [ "$is_breaking" = true ]; then
    final_message="$final_message\n\nBREAKING CHANGE: $breaking_summary"
fi

echo -e "\n${GREEN}Committing with message:${NC}"
echo -e "$final_message"
echo -e "$final_message" | git commit -F -

echo -e "\n${BLUE}Pushing to origin $branch_name...${NC}"
git push -u origin "$branch_name"

echo -e "\n${GREEN}=========================================${NC}"
echo -e "${GREEN} Mission accomplished                     ${NC}"
echo -e "${GREEN}=========================================${NC}"
