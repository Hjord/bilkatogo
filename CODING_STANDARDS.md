# Coding standards

Rules the reviewer applies to a diff. Anything a tool can check (ruff, ty, tests) lives in that tool instead.

## Domain terms

- A field named after a `GLOSSARY.md` term reads the source the glossary names for it, in every model. When two models fill the same term from different Bilka fields (the Article Number from `objectID` in one and from Algolia's `article` in another), that is a bug, not a style difference. A term whose source the glossary does not name gets its source added to the glossary in the same change.
