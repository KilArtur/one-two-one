#!/bin/bash
set -e

TASKS_FILE="tasks.json"

# =============================================================================
# ralph.sh — инкрементальный прогон задач из tasks.json одним из агентов.
#
# Использование:
#   ./ralph.sh [КОЛИЧЕСТВО] [АГЕНТ]
#   ./ralph.sh --count N --agent claude|codex
#
# Примеры:
#   ./ralph.sh            # все оставшиеся задачи, агент — автоопределение
#   ./ralph.sh 5 codex    # выполнить 5 задач через codex
#   ./ralph.sh 3 claude   # выполнить 3 задачи через claude
#   ./ralph.sh -n 5 -a codex
#
# КОЛИЧЕСТВО = 0 или "all" означает «без лимита» (пока есть pending-задачи).
# АГЕНТ можно также задать через переменную окружения RALPH_AGENT.
# =============================================================================

LIMIT=0                       # 0 = без лимита
AGENT="${RALPH_AGENT:-}"      # пусто = автоопределение

print_usage() {
    sed -n '6,22p' "$0" | sed 's/^# \{0,1\}//'
}

# ---- Разбор аргументов (флаги + позиционные) --------------------------------
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--count)  LIMIT="$2"; shift 2 ;;
        -a|--agent)  AGENT="$2"; shift 2 ;;
        -h|--help)   print_usage; exit 0 ;;
        -*)          echo "Неизвестный флаг: $1" >&2; print_usage; exit 1 ;;
        *)           POSITIONAL+=("$1"); shift ;;
    esac
done
[[ ${#POSITIONAL[@]} -ge 1 ]] && LIMIT="${POSITIONAL[0]}"
[[ ${#POSITIONAL[@]} -ge 2 ]] && AGENT="${POSITIONAL[1]}"

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

# ---- Старт ------------------------------------------------------------------
agent=$(resolve_agent) || exit 1

baseline_done=$(count_status done)
if [[ "$LIMIT" -gt 0 ]]; then
    echo "Агент: $agent | Выполнить задач за запуск: $LIMIT"
else
    echo "Агент: $agent | Выполнить задач за запуск: все оставшиеся"
fi
echo "==================================="

iteration=1

while has_pending_tasks; do
    # Проверка лимита выполненных за этот запуск задач
    completed_this_run=$(( $(count_status done) - baseline_done ))
    if [[ "$LIMIT" -gt 0 && "$completed_this_run" -ge "$LIMIT" ]]; then
        echo "Достигнут лимит: за этот запуск выполнено $completed_this_run задач(и)."
        notify "Лимит достигнут. Готово."
        exit 0
    fi

    echo "Итерация $iteration"
    echo "-----------------------------------"
    echo "Задач pending: $(count_status pending), done: $(count_status done) (за запуск: $completed_this_run/${LIMIT:-∞})"
    echo "-----------------------------------"

    prompt=$(cat <<'EOF'
@tasks.json @progress.md
1. Найди фичу с наивысшим приоритетом и работай ТОЛЬКО над ней.
Это должна быть фича, которую ТЫ считаешь наиболее приоритетной — не обязательно первая в списке.
Проверь, что все её dependencies имеют статус done; если нет — выбери другую задачу.
2. Проверь, что типы проходят через 'uv run ruff check .' и тесты через 'uv run pytest'.
3. Обнови TASK с информацией о выполненной работе (смени status на done ТОЛЬКО после прохождения всех test_steps).
4. Добавь свой прогресс в файл progress.md.
Используй это, чтобы оставить заметку для следующей итерации работы над кодом.
5. Сделай git commit для этой фичи.
РАБОТАЙ ТОЛЬКО НАД ОДНОЙ ФИЧЕЙ.
Если при реализации фичи ты заметишь, что TASK полностью выполнен, выведи <promise>COMPLETE</promise>.
EOF
)

    result=$(run_agent "$agent" "$prompt")
    echo "$result"

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
