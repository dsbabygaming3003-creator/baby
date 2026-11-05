// TITAN OMEGA INFINITY V18 — APK signer wrapper.
//
// Uses `apk_sign_ts` (MIT) to produce a JAR (v1) + APK Signature Scheme v2/v3
// signature from a JKS keystore. The signer is a build-time tool only; it is
// not part of the shipped application.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    if (key.endsWith("-pass")) {
      args[key] = argv[i + 1];
      i += 1;
    } else if (key === "keystore" || key === "ks-key-alias" || key === "input" || key === "output") {
      args[key] = argv[i + 1];
      i += 1;
    } else {
      args[key] = true;
    }
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));

if (!args.input || !args.output) {
  console.error("usage: node sign_apk.mjs --input IN.apk --output OUT.apk --keystore K.jks --ks-pass P --key-pass P --ks-key-alias A");
  process.exit(2);
}

const keystorePath = args.keystore;
if (!keystorePath || !existsSync(keystorePath)) {
  console.error(`keystore not found: ${keystorePath}`);
  process.exit(3);
}

const password = args["ks-pass"];
const alias = args["ks-key-alias"];

// Extract the certificate + private key from the JKS using the JDK's keytool
// (JKS -> PEM). keytool ships in the JRE that the toolchain already provides.
const keytool = process.env.TITAN_KEYTOOL || "/opt/titan/toolchain/jdk/bin/keytool";
const tmp = `/tmp/titan-sign-${process.pid}`;
execFileSync("mkdir", ["-p", tmp]);
execFileSync(keytool, ["-importkeystore", "-srckeystore", keystorePath, "-srcstorepass", password,
  "-destkeystore", `${tmp}/key.p12`, "-deststoretype", "PKCS12", "-deststorepass", password]);

// PKCS12 -> PEM (private key + certificate) via openssl.
execFileSync("openssl", ["pkcs12", "-in", `${tmp}/key.p12`, "-passin", `pass:${password}`,
  "-nocerts", "-nodes", "-out", `${tmp}/key.pem`]);
execFileSync("openssl", ["pkcs12", "-in", `${tmp}/key.p12`, "-passin", `pass:${password}`,
  "-nokeys", "-out", `${tmp}/cert.pem`]);

const mod = require("/opt/titan/toolchain/apksigner/dist/index.js");
const { ApkSigner, SigningKey, convertToPEM } = mod;

const apk = new Uint8Array(readFileSync(args.input));
const pem = convertToPEM ? await convertToPEM(new Uint8Array(readFileSync(keystorePath)), password, "jks") : null;

let signingKey;
if (pem && pem.privateKey && pem.certificate) {
  signingKey = SigningKey.fromPEM(pem.privateKey, pem.certificate);
} else {
  signingKey = SigningKey.fromPEM(
    readFileSync(`${tmp}/key.pem`, "utf8"),
    readFileSync(`${tmp}/cert.pem`, "utf8")
  );
}

const signer = new ApkSigner({ signingKey });
const result = await signer.sign(apk);
writeFileSync(args.output, Buffer.from(result.signedApk));
console.log(`signed -> ${args.output} (${result.signedApk.length} bytes)`);
execFileSync("rm", ["-rf", tmp]);
