# CATS-Reborn Windows build preparation

This source bundle includes a generated `MultiCarrierManager/ApiTools/OAuth2.cs` configured with the Frontier Client ID and App Name supplied by the repository owner. The Client ID is an application identifier, not a client secret. No client secret was supplied or added.

## Build using GitHub Actions

1. Commit and push the contents of this folder to the `OniReisu/CATS-Reborn` repository (merge with your existing repository rather than replacing unrelated newer work).
2. Open **Actions** and run **Build CATS-Reborn (Windows)** using **Run workflow**, or push a version tag such as `v1.0.0`.
3. Download the `CATS-Reborn-Windows-x64` artifact from the completed workflow run.
4. Test the portable ZIP on a clean Windows machine before publishing it as a GitHub Release.

The workflow builds the Python traversal executable, compiles the .NET Framework 4.7.2 application, and packages the resulting output folder. It does not publish a GitHub Release automatically.

## Important

This is build automation preparation, not a verified compiled release. The project has not yet been compiled or runtime-tested in this environment. The workflow may reveal further dependency or source compatibility issues that need fixing.
