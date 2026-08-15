#!/usr/bin/env bash
#
# Verify every toolchain in the CSCI-350 image actually runs.
# Compiles/evaluates a trivial program per language — presence on PATH is not
# enough, since a half-installed GHC or Racket will still answer --version.
#
# Usage:  ./smoke-test.sh          (inside the container)
#         docker run --rm IMAGE smoke-test
set -uo pipefail

pass=0; fail=0
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

check() {   # check <label> <command...>
  local label="$1"; shift
  if out="$("$@" 2>&1)"; then
    printf '  \033[32mok\033[0m   %-16s %s\n' "$label" "$(head -1 <<<"$out")"
    pass=$((pass+1))
  else
    printf '  \033[31mFAIL\033[0m %-16s %s\n' "$label" "$(head -3 <<<"$out" | tr '\n' ' ')"
    fail=$((fail+1))
  fi
}

echo "== versions =="
check java      java -version
check javac     javac -version
check racket    racket --version
check sbcl      sbcl --version
check swipl     swipl --version
check ghc       ghc --version
check cabal     cabal --version
check hls       haskell-language-server-wrapper --version
check python    python3 --version
check pytest    pytest --version

echo
echo "== junit jar =="
if [ -f "${JUNIT_JAR:-/opt/junit/junit-platform-console-standalone.jar}" ]; then
  printf '  \033[32mok\033[0m   %-16s %s\n' "junit" "${JUNIT_JAR}"
  pass=$((pass+1))
else
  printf '  \033[31mFAIL\033[0m %-16s not found at %s\n' "junit" "${JUNIT_JAR:-unset}"
  fail=$((fail+1))
fi

echo
echo "== each language actually executes =="

cat > "$tmp/Hello.java" <<'EOF'
public class Hello { public static void main(String[] a){ System.out.println("java ok"); } }
EOF
check "java run"   bash -c "cd '$tmp' && javac Hello.java && java Hello"

# A .rkt file is a module, so the #lang line is required — a bare expression
# fails with "expected a `module' declaration".
printf '#lang racket/base\n(displayln "racket ok")\n' > "$tmp/t.rkt"
check "racket run" racket "$tmp/t.rkt"

# Common Lisp path — the dialect Paul's inherited HW 02 is written in.
echo '(progn (format t "sbcl ok~%") (sb-ext:quit))' > "$tmp/t.lisp"
check "sbcl run"   sbcl --script "$tmp/t.lisp"

cat > "$tmp/t.pl" <<'EOF'
:- initialization(main).
main :- write('prolog ok'), nl, halt.
EOF
check "prolog run" swipl -q "$tmp/t.pl"

echo 'main = putStrLn "haskell ok"' > "$tmp/t.hs"
check "haskell run" bash -c "cd '$tmp' && runghc t.hs"

echo 'print("python ok")' > "$tmp/t.py"
check "python run" python3 "$tmp/t.py"

echo
echo "== level runner =="
check "level"  level --version
check "pyyaml" python3 -c "import yaml"

echo
if [ "$fail" -eq 0 ]; then
  printf '\033[32mall %d checks passed\033[0m\n' "$pass"
else
  printf '\033[31m%d passed, %d FAILED\033[0m\n' "$pass" "$fail"
fi
exit $(( fail > 0 ))
