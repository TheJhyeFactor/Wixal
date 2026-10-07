import encodings.idna  # HTTP host names load this codec dynamically in the bundled engine.
import encodings.utf_16_le  # Command offsets match Swift UTF-16 strings in the frozen helper.
import sys
from wixal.service import main
from wixal.cli import main as terminal_main
from wixal.companion_cli import main as companion_main
if __name__ == "__main__":
    if "--supervise-runtime" in sys.argv:
        from wixal.supervisor import main as supervisor_main
        sys.exit(supervisor_main())
    elif "--background" in sys.argv:
        sys.argv.remove("--background")
        from wixal.scheduling import main as background_main
        background_main()
    elif "--companion" in sys.argv:
        sys.argv.remove("--companion")
        companion_main()
    elif "--terminal" in sys.argv:
        sys.argv.remove("--terminal")
        terminal_main()
    else:
        main()
