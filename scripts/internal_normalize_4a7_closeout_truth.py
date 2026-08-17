from pathlib import Path

path = Path("to_do_update_list.md")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "main@3971244255fb3045a8cb6981a00acaccd1f8841b\nPR #165 Research Memory merged",
    "accepted product tree@3971244255fb3045a8cb6981a00acaccd1f8841b\ncurrent main: re-query remote truth; closeout handoff may be a documentation-only descendant\nPR #165 Research Memory merged",
    1,
)
text = text.replace("### Exact current-main verification", "### Accepted product-tree verification", 1)
text = text.replace(
    "Current production candidate `3971244255fb3045a8cb6981a00acaccd1f8841b` is verified:",
    "Accepted 4A-7 production product tree `3971244255fb3045a8cb6981a00acaccd1f8841b` is verified:",
    1,
)
text = text.replace(
    "GitHub combined statuses on the exact main are `Vercel: success` and `Cloudflare Worker: success`.",
    "GitHub combined statuses on the accepted product-tree commit are `Vercel: success` and `Cloudflare Worker: success`.",
    1,
)
text = text.replace(
    "the internal acceptance branch is content-identical to current main after cleanup.",
    "the internal acceptance branch is content-identical to the accepted product tree after cleanup.",
    1,
)
path.write_text(text, encoding="utf-8")
