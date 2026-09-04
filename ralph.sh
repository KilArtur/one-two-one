#!/bin/bash
set -e

TASKS_FILE="tasks.json"
TASK_OWNERS_FILE="task-owners.json"

# =============================================================================
# ralph.sh — инкрементальный прогон задач из tasks.json одним из агентов.
#
# Использование:
#   ./ralph.sh [КОЛИЧЕСТВО] [АГЕНТ] [ИСПОЛНИТЕЛЬ]
#   ./ralph.sh --count N --agent claude|codex --worker <имя>
#
# Примеры:
#   ./ralph.sh            # все оставшиеся задачи, агент — автоопределение
#   ./ralph.sh 5 codex    # выполнить 5 задач через codex
#   ./ralph.sh 3 claude   # выполнить 3 задачи через claude
#   ./ralph.sh -n 5 -a codex -w artur
#
# КОЛИЧЕСТВО = 0 или "all" означает «без лимита» (пока есть pending-задачи).
# АГЕНТ можно также задать через переменную окружения RALPH_AGENT.
# ИСПОЛНИТЕЛЯ можно задать через переменную окружения RALPH_WORKER.
# =============================================================================

LIMIT=0                       # 0 = без лимита
AGENT="${RALPH_AGENT:-}"      # пусто = автоопределение
WORKER="${RALPH_WORKER:-${USER:-worker}}"
LOCK_DIR=".ralph.lock"

print_usage() {
    sed -n '6,22p' "$0" | sed 's/^# \{0,1\}//'
}

# ---- Разбор аргументов (флаги + позиционные) --------------------------------
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--count)  LIMIT="$2"; shift 2 ;;
        -a|--agent)  AGENT="$2"; shift 2 ;;
        -w|--worker) WORKER="$2"; shift 2 ;;
        -h|--help)   print_usage; exit 0 ;;
        -*)          echo "Неизвестный флаг: $1" >&2; print_usage; exit 1 ;;
        *)           POSITIONAL+=("$1"); shift ;;
    esac
done
[[ ${#POSITIONAL[@]} -ge 1 ]] && LIMIT="${POSITIONAL[0]}"
[[ ${#POSITIONAL[@]} -ge 2 ]] && AGENT="${POSITIONAL[1]}"
[[ ${#POSITIONAL[@]} -ge 3 ]] && WORKER="${POSITIONAL[2]}"

# "all" -> без лимита
[[ "$LIMIT" == "all" ]] && LIMIT=0

# Валидация LIMIT — неотрицательное целое
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
    echo "КОЛИЧЕСТВО должно быть неотрицательным целым числом (или 'all'). Получено: '$LIMIT'" >&2
    exit 1
fi

# ---- Выбор агента -----------------------------------------------------------
# Если агент задан явно — проверяем, что он установлен.
# Иначе автоопределение (предпочитаем claude).
resolve_agent() {
    local a="$AGENT"
    if [[ -z "$a" ]]; then
        if command -v claude >/dev/null 2>&1; then
            a="claude"
        elif command -v codex >/dev/null 2>&1; then
            a="codex"
        else
            echo "Не найден ни 'claude', ни 'codex'. Установите один из них или задайте --agent." >&2
            return 1
        fi
    fi
    case "$a" in
        claude|codex) ;;
        *) echo "Неподдерживаемый агент: '$a'. Допустимо: claude | codex." >&2; return 1 ;;
    esac
    if ! command -v "$a" >/dev/null 2>&1; then
        echo "Агент '$a' выбран, но команда не найдена в PATH. Установите его." >&2
        return 1
    fi
    echo "$a"
}

run_agent() {
    local agent="$1"
    local prompt="$2"

    case "$agent" in
        claude)
            claude --permission-mode acceptEdits -p "$prompt"
            ;;
        codex)
            local output_file
            output_file="$(mktemp -t ralph_codex.XXXXXX)"
            # Non-interactive Codex exec, забираем только последнее сообщение.
            codex exec --full-auto --color never -C "$PWD" --output-last-message "$output_file" "$prompt" >/dev/null
            cat "$output_file"
            rm -f "$output_file"
            ;;
        *)
            echo "Unsupported agent: $agent" >&2
            return 1
            ;;
    esac
}

# Голосовое уведомление (безопасно, если 'say' недоступен — напр. на Linux).
notify() {
    if command -v say >/dev/null 2>&1; then
        say -v Milena "$1" 2>/dev/null || true
    fi
}

count_status() {
    local n
    n=$(grep -c "\"status\": \"$1\"" "$TASKS_FILE" 2>/dev/null) || true
    echo "${n:-0}"
}

has_pending_tasks() {
    [ "$(count_status pending)" -gt 0 ]
}

acquire_lock() {
    while ! mkdir "$LOCK_DIR" 2>/dev/null; do
        sleep 0.1
    done
}

release_lock() {
    rmdir "$LOCK_DIR" 2>/dev/null || true
}

claim_next_task() {
    local worker="$1"
    acquire_lock
    python3 - "$TASKS_FILE" "$TASK_OWNERS_FILE" "$worker" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

tasks_file, owners_file, worker = sys.argv[1], sys.argv[2], sys.argv[3]

with open(tasks_file, "r", encoding="utf-8") as fh:
    data = json.load(fh)

owners = {}
if os.path.exists(owners_file):
    with open(owners_file, "r", encoding="utf-8") as fh:
        owners_data = json.load(fh)
    for owner, task_ids in owners_data.get("workers", {}).items():
        for task_id in task_ids:
            owners[task_id] = owner

priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
critical_path = {task_id: idx for idx, task_id in enumerate(data.get("critical_path", []))}


def task_sort_key(task):
    return (
        priority_order.get(task.get("priority"), 99),
        critical_path.get(task["id"], 10**9),
        task["id"],
    )


def dependencies_done(task, done_ids):
    return all(dep in done_ids for dep in task.get("dependencies", []))


tasks = data.get("tasks", [])
done_ids = {task["id"] for task in tasks if task.get("status") == "done"}

for task in tasks:
    if task.get("status") == "in_progress" and task.get("assignee") == worker:
        print(task["id"])
        break
else:
    candidates = [
        task
        for task in tasks
        if task.get("status") == "pending" and dependencies_done(task, done_ids)
        and (not owners or owners.get(task["id"]) == worker)
    ]
    if not candidates:
        print("")
        sys.exit(0)

    chosen = min(candidates, key=task_sort_key)
    chosen["status"] = "in_progress"
    chosen["assignee"] = worker
    chosen["claimed_at"] = datetime.now(timezone.utc).isoformat()

    with open(tasks_file, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(chosen["id"])
PY
    release_lock
}

task_status() {
    python3 - "$TASKS_FILE" "$1" <<'PY'
import json
import sys

tasks_file, task_id = sys.argv[1], sys.argv[2]
with open(tasks_file, "r", encoding="utf-8") as fh:
    data = json.load(fh)

for task in data.get("tasks", []):
    if task.get("id") == task_id:
        print(task.get("status", ""))
        break
PY
}

# ---- Старт ------------------------------------------------------------------
agent=$(resolve_agent) || exit 1
trap release_lock EXIT

baseline_done=$(count_status done)
if [[ "$LIMIT" -gt 0 ]]; then
    echo "Агент: $agent | Исполнитель: $WORKER | Выполнить задач за запуск: $LIMIT"
else
    echo "Агент: $agent | Исполнитель: $WORKER | Выполнить задач за запуск: все оставшиеся"
fi
echo "==================================="

iteration=1

while true; do
    # Проверка лимита выполненных за этот запуск задач
    completed_this_run=$(( $(count_status done) - baseline_done ))
    if [[ "$LIMIT" -gt 0 && "$completed_this_run" -ge "$LIMIT" ]]; then
        echo "Достигнут лимит: за этот запуск выполнено $completed_this_run задач(и)."
        notify "Лимит достигнут. Готово."
        exit 0
    fi

    task_id="$(claim_next_task "$WORKER")"
    if [[ -z "$task_id" ]]; then
        if has_pending_tasks; then
            echo "Нет доступных задач для исполнителя '$WORKER': оставшиеся pending либо забронированы, либо ждут dependencies."
        else
            echo "Все задачи выполнены! Итераций: $((iteration-1))"
            notify "Хозяин, я сделалъ!"
        fi
        exit 0
    fi

    echo "Итерация $iteration"
    echo "-----------------------------------"
    echo "Задача: $task_id"
    echo "Задач pending: $(count_status pending), in_progress: $(count_status in_progress), done: $(count_status done) (за запуск: $completed_this_run/${LIMIT:-∞})"
    echo "-----------------------------------"

    prompt=$(cat <<'EOF'
@tasks.json @progress.md
1. Работай ТОЛЬКО над уже забронированной задачей TASK_ID_PLACEHOLDER.
Не выбирай другую задачу и не меняй assignee у других задач.
2. Проверь, что типы проходят через 'uv run ruff check .' и тесты через 'uv run pytest'.
3. Обнови запись этой TASK в tasks.json: оставь status=in_progress, если задача не завершена; смени status на done ТОЛЬКО после прохождения всех test_steps.
4. Добавь свой прогресс в файл progress.md.
Используй это, чтобы оставить заметку для следующей итерации работы над кодом.
5. Сделай git commit для этой фичи.
РАБОТАЙ ТОЛЬКО НАД ОДНОЙ ФИЧЕЙ.
Если при реализации фичи ты заметишь, что TASK полностью выполнен, выведи <promise>COMPLETE</promise>.
EOF
)
    prompt="${prompt/TASK_ID_PLACEHOLDER/$task_id}"

    result=$(run_agent "$agent" "$prompt")
    echo "$result"

    current_status="$(task_status "$task_id")"
    if [[ "$result" == *"<promise>COMPLETE</promise>"* && "$current_status" != "done" ]]; then
        echo "TASK $task_id помечена как COMPLETE в ответе агента, но status в tasks.json = '$current_status'. Останавливаюсь."
        exit 1
    fi
    if [[ "$current_status" != "done" && "$result" != *"<promise>COMPLETE</promise>"* ]]; then
        echo "TASK $task_id осталась в статусе '$current_status'. Останавливаюсь: задача закреплена за '$WORKER'."
        exit 0
    fi

    if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
        echo "✓ TASK выполнен!"
        remaining=$(count_status pending)
        completed_this_run=$(( $(count_status done) - baseline_done ))
        if [ "$remaining" -eq 0 ]; then
            echo "🎉 Все задачи выполнены!"
            notify "Хозяин, я всё сделалъ!"
            exit 0
        fi
        if [[ "$LIMIT" -gt 0 && "$completed_this_run" -ge "$LIMIT" ]]; then
            echo "Достигнут лимит ($LIMIT). Осталось pending: $remaining."
            notify "Лимит достигнут. Продолжу в следующий раз."
            exit 0
        fi
        echo "Осталось задач: $remaining. Продолжаю..."
        notify "Задача готова. Продолжаю работу."
    fi

    ((iteration++))
done

echo "Все задачи выполнены! Итераций: $((iteration-1))"
notify "Хозяин, я сделалъ!"
