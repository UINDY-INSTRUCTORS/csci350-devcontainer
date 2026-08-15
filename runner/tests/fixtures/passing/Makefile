.PHONY: test-smoke test-parse test-eval test-prop
test-smoke:
	@echo smoke ok
test-parse:
	@echo parse ok
test-eval:
	@if [ -f FAIL_EVAL ]; then echo eval broke; exit 1; else echo eval ok; fi
test-prop:
	@echo "prop ok seed=$$LEVEL_SEED"
