/** Refuse the next paid agent after the pipeline requests a cooperative stop. */
const DRIVER_SURFACE_SCHEMA = "skills/pipeline-contracts/schemas/driver-surface.schema.json";
const STOP_FILE_CONSTANT = "STOP_FILE_ENV";
/**
 * The hook runtime's $.env.get accepts only a string literal (claude plugin validate
 * reads the names off the source), so the variable is spelled here and checked once
 * against the driver-surface schema, the contract's one place, before it is trusted.
 */
const STOP_FILE_VARIABLE = "ATW_STOP_FILE";

/**
 * The settled verdict of the schema comparison, memoized at module scope: null while
 * unsettled, { drift: null } when the schema agrees, { drift: reason } when it does not.
 * A read or parse failure is not settled, so the next spawn reads the schema again.
 * @type {{ drift: string | null } | null}
 */
let contractVerdict = null;
/** @type {Promise<{ drift: string | null, settled: boolean }> | null} */
let pendingCheck = null;

/**
 * Compare STOP_FILE_VARIABLE with the DriverEnvironment property the schema marks
 * with x-constant STOP_FILE_ENV. Resolves { drift: null, settled: true } when they
 * agree, { drift, settled: true } when the parsed schema disagrees, and
 * { drift, settled: false } when the schema cannot be read or parsed.
 */
async function readContractDrift($) {
  const path = `${$.plugin.root}/${DRIVER_SURFACE_SCHEMA}`;
  let schema;
  try {
    schema = JSON.parse(await $.fs.read(path));
  } catch (error) {
    return {
      drift: `cannot read ${path}: ${error instanceof Error ? error.message : String(error)}`,
      settled: false,
    };
  }
  const properties = schema?.$defs?.DriverEnvironment?.properties;
  if (properties === null || typeof properties !== "object") {
    return { drift: `${DRIVER_SURFACE_SCHEMA} has no $defs.DriverEnvironment.properties`, settled: true };
  }
  const names = Object.entries(properties)
    .filter(([, spec]) => spec !== null && typeof spec === "object" && spec["x-constant"] === STOP_FILE_CONSTANT)
    .map(([name]) => name);
  if (names.length !== 1) {
    return {
      drift: `${DRIVER_SURFACE_SCHEMA} names ${names.length} DriverEnvironment properties for ${STOP_FILE_CONSTANT}, expected 1`,
      settled: true,
    };
  }
  if (names[0] !== STOP_FILE_VARIABLE) {
    return {
      drift: `${DRIVER_SURFACE_SCHEMA} names ${names[0]} for ${STOP_FILE_CONSTANT}; this hook reads ${STOP_FILE_VARIABLE}`,
      settled: true,
    };
  }
  return { drift: null, settled: true };
}

/** Resolve the memoized drift verdict, reading the schema only until it settles. */
async function contractDrift($) {
  if (contractVerdict !== null) {
    return contractVerdict.drift;
  }
  pendingCheck ??= readContractDrift($);
  const result = await pendingCheck;
  pendingCheck = null;
  if (result.settled) {
    contractVerdict = { drift: result.drift };
  }
  return result.drift;
}

export function register(on) {
  on("agent.spawn", async ($, event, next) => {
    const drift = await contractDrift($);
    if (drift !== null) {
      return { deny: `Stop-file contract check failed; no agent may start until it is fixed: ${drift}` };
    }
    const stopFile = await $.env.get("ATW_STOP_FILE");
    if (!stopFile) {
      return next(event);
    }
    const stopped = await $.fs.exists(stopFile).then(
      (exists) => (exists ? "Pipeline stop requested; no further agent may start." : null),
      (error) => `Cannot test stop file ${stopFile}: ${error instanceof Error ? error.message : String(error)}`,
    );
    if (stopped !== null) {
      return { deny: stopped };
    }
    return next(event);
  });
}
