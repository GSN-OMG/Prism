.PHONY: help setup test lint fmt

help:
	@$(MAKE) -C phase3 help

setup:
	@$(MAKE) -C phase3 setup

test:
	@$(MAKE) -C phase3 test

lint:
	@$(MAKE) -C phase3 lint

fmt:
	@$(MAKE) -C phase3 fmt

