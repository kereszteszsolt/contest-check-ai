# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import sys

sys.path.insert(0, "/opt/cca-worker")

from contest_check.judge.cli import main  # noqa: E402

main()
