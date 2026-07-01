class ExitReporter {
    onRunComplete(contexts, results) {
        if (results.numFailedTests === 0 && results.numRuntimeErrorTestSuites === 0) {
            console.log('\n✅ All tests passed. Forcing exit 0 to bypass Node 20 Jest worker leaks.');
            setTimeout(() => process.exit(0), 500);
        }
    }
}
module.exports = ExitReporter;
