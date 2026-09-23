# Development disclosures

- OpenAI Codex generated and reviewed source code and documentation at the repository owner's request. Codex processed repository content as context.
- The organizer's original README title and team description are retained.
- Dependencies and licenses are recorded in `package-lock.json`. Technical sources include official [Node.js](https://nodejs.org/en/about/previous-releases), [Vite](https://vite.dev/guide/), [Tailwind](https://tailwindcss.com/docs/installation/using-vite), [Express](https://expressjs.com/en/5x/api/), [Zod](https://zod.dev/basics), [OpenAI SDK](https://developers.openai.com/api/reference/typescript), [Docker](https://docs.docker.com/build/concepts/context/), [checkout](https://github.com/actions/checkout/tree/v7.0.1) and [setup-node](https://github.com/actions/setup-node/tree/v7.0.0) documentation. No proprietary project code was copied.
- [Energy references](docs/energy/README.md) use hypothetical examples, with sources listed in their [reference index](docs/energy/references.md). They do not establish official requirements or actual dataset semantics. No real dataset, model weights, tariff or emissions factor was imported.
- The application's OpenAI integration has been tested with mocked transport only. No live or paid application AI request was made, and no competition dataset was sent through that integration. This is separate from Codex's use of repository context during development.

## Verification limits

Docker image/container execution, live OpenAI access and remote GitHub Actions remain unverified. No browser-test runner is configured. No deployment or push has been performed. Local checks and remaining gaps are recorded in [integration verification](docs/hackathon/integration-verification.md).
