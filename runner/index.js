/*
 * fork-sentry-runner
 *
 * 		This is the main Actions runner built when
 *		integrated with CI/CD. Will consume the necessary
 *		app tokens to interact with the cloud-based infrastructure.
 */
const https = require('https');
const core = require('@actions/core');
const github = require('@actions/github');

try {
  const github_token = core.getInput('github_token');
  const fork_sentry_token = core.getInput('fork_sentry_token');
  const endpoint_url = core.getInput('infra_endpoint');

  // Get the JSON webhook payload for the event that triggered the workflow
  const {owner, name} = github.context.repo();

  // send request to dispatcher to kick off analysis
  const time = (new Date()).toTimeString();
  console.log(`Starting fork integrity analysis at ${time}`);

  const data = new TextEncoder().encode(
    JSON.stringify({
        owner: owner,
        name: name,
        github_token: github_token,
        api_token: fork_sentry_token,
    })
  );

  const options = {
    hostname: endpoint_url,
    port: 443,
    path: "/dispatch",
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Content-Length": data.length
    }
  }

  const req = https.request(options, res => {
	console.log(`statusCode: ${res.statusCode}`)
    res.on('data', d => {
      process.stdout.write(d)
    })
  });

  req.on('error', error => {
	  console.error(error)
  })
  
  req.write(data);
  req.end();
  console.log("Done! Comment alerts will be created if suspicious forks show up");

} catch (error) {
  core.setFailed(error.message);
}
