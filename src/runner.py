"""Ejecucion sin servidor: sincroniza estado R2 -> pipeline -> estado R2."""
import sys
import logging
from src import state_store
from src.main import run, publish_from_disk

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("VideoFactory.Runner")


def main():
    args = sys.argv[1:]
    use_sync = "--no-sync" not in args
    draft = "--draft" in args
    skip_intel = "--skip-intelligence" in args
    publish_only = "--publish-only" in args

    if use_sync:
        log.info("Sincronizando estado desde R2...")
        state_store.pull_state()

    exit_code = 0
    try:
        if publish_only:
            publish_from_disk()
        else:
            run(draft=draft, skip_intelligence=skip_intel)
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except Exception as e:
        log.error(f"Pipeline fallo: {e}")
        exit_code = 1
    finally:
        if use_sync:
            log.info("Sincronizando estado hacia R2...")
            try:
                state_store.push_state()
            except Exception as e:
                log.error(f"Fallo el push de estado: {e}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
