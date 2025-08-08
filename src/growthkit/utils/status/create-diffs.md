# Creating project status updates via git diffs
Logs and diffs should be treated as first class citizens when summarizing project sessions.
Multi turn chat conversations used to add context to the first class citizens.

## Commands
```sh
git log --since=2.days --until=yesterday --date=local --reverse -p > session-1.diff
git log --since=yesterday --date=local --reverse -p > session.diff
 ```

Tip: It's easier to get an idea of what dates to choose by looking at github repo history.
Note: Because of UTC sometimes the dates do not match local time.

## Prompting for Summary
`Create a status @end-session.md based on @session.diff`

## Committing Summary
Upload as `project status update`