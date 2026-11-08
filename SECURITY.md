# Security

These skills run inside AI agents that hold a user's BrainSTEM API token and can write research records.
We take reports about them seriously.

## Reporting a vulnerability

Report privately through GitHub: open the repository's **Security** tab and choose **Report a
vulnerability**. Please do not open a public issue for a security problem.

Useful reports include:

- skill or reference text that leads an agent to print, store or send a token, or to ask for a password;
- instructions that let content stored in BrainSTEM records (names, notes, attachments) steer the agent
  into actions the user did not ask for;
- paths that let an agent write, delete or change records without a confirmed change plan;
- problems in `tools/` or the test harness that leak credentials.

Vulnerabilities in the BrainSTEM server or the Python client belong to those projects; if you are unsure
where a problem lies, report it here and we will route it.

## Supported versions

Only the latest release of the skills receives fixes.
