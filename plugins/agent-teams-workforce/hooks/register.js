/** Refuse the next paid agent after the pipeline requests a cooperative stop. */
export function register(on) {
  on("agent.spawn", async ($, event, next) => {
    const stopFile = await $.env.get("ATW_STOP_FILE");
    if (stopFile && await $.fs.exists(stopFile)) {
      return { deny: "Pipeline stop requested; no further agent may start." };
    }
    return next(event);
  });
}
