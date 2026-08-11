"""Contract tests for the signed FlamaAudio Windows release pipeline."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "flama-audio-release.yml"
SIGN_SCRIPT_PATH = ROOT / "flama-audio" / "scripts" / "Sign-WindowsRelease.ps1"
VERIFY_SCRIPT_PATH = ROOT / "flama-audio" / "scripts" / "Test-WindowsRelease.ps1"


class TestFlamaAudioReleaseWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.sign_script = SIGN_SCRIPT_PATH.read_text(encoding="utf-8")
        cls.verify_script = VERIFY_SCRIPT_PATH.read_text(encoding="utf-8")

    def test_production_signing_runs_only_for_release_tags_or_manual_release(self):
        self.assertIn('tags:\n      - "flama-audio-v*"', self.workflow)
        self.assertIn("workflow_dispatch:", self.workflow)
        self.assertNotIn("pull_request:", self.workflow)
        self.assertNotIn("branches:\n      - master", self.workflow)
        self.assertIn("environment: Flama", self.workflow)

    def test_builds_portable_self_contained_single_file_without_trimming(self):
        self.assertIn("PublishSingleFile=true", self.workflow)
        self.assertIn("SelfContained=true", self.workflow)
        self.assertIn("PublishReadyToRun=false", self.workflow)
        self.assertIn("PublishTrimmed=false", self.workflow)
        self.assertIn("flama-audio/publish/release/FlamaAudio-Portable.exe", self.workflow)
        self.assertNotIn("Inno Setup", self.workflow)
        self.assertNotIn("FlamaAudio-Setup.exe", self.workflow)

    def test_signs_final_binary_with_sha256_and_rfc3161_timestamp(self):
        self.assertIn("WINDOWS_SIGNING_CERTIFICATE_BASE64", self.workflow)
        self.assertIn("WINDOWS_SIGNING_CERTIFICATE_PASSWORD", self.workflow)
        self.assertIn("WINDOWS_SIGNING_CERTIFICATE_THUMBPRINT", self.workflow)
        self.assertIn("/fd SHA256", self.sign_script)
        self.assertIn("/tr $TimestampUrl", self.sign_script)
        self.assertIn("/td SHA256", self.sign_script)
        self.assertIn("/sha1 $actualThumbprint", self.sign_script)
        self.assertNotIn("/p $certificatePassword", self.sign_script)

    def test_release_order_prevents_post_signing_binary_mutation(self):
        prepare = self.workflow.index("name: Prepare final portable binary")
        sign = self.workflow.index("name: Sign final EXE with Authenticode")
        verify = self.workflow.index("name: Verify signed EXE and record identity")
        package = self.workflow.index("name: Package signed EXE and create SHA256 metadata")
        extract_verify = self.workflow.index(
            "name: Extract package and verify embedded signed EXE"
        )
        publish = self.workflow.index("name: Publish GitHub Release")
        deploy = self.workflow.index(
            "name: Deploy signed EXE and checksum to Flama download server"
        )
        self.assertLess(prepare, sign)
        self.assertLess(sign, verify)
        self.assertLess(verify, package)
        self.assertLess(package, extract_verify)
        self.assertLess(extract_verify, publish)
        self.assertLess(publish, deploy)
        self.assertEqual(self.workflow.count("dotnet publish"), 1)
        self.assertIn('throw "The EXE changed after Authenticode signing."', self.workflow)

    def test_requires_both_authenticode_verifiers_and_timestamp(self):
        self.assertIn("signtool.exe", self.verify_script.lower())
        self.assertIn("verify /pa /all /v /tw", self.verify_script)
        self.assertIn("Get-AuthenticodeSignature", self.verify_script)
        self.assertIn('Status -ne "Valid"', self.verify_script)
        self.assertIn("TimeStamperCertificate", self.verify_script)

    def test_pfx_is_ephemeral_and_never_uploaded(self):
        self.assertIn("Import-PfxCertificate", self.sign_script)
        self.assertIn("finally", self.sign_script)
        self.assertIn("Remove-Item -LiteralPath $pfxPath", self.sign_script)
        self.assertIn("Cert:\\CurrentUser\\My", self.sign_script)
        upload_block = self.workflow.split(
            "name: Upload verified workflow artifact", maxsplit=1
        )[1].split("name: Publish GitHub Release", maxsplit=1)[0]
        self.assertNotIn(".pfx", upload_block.lower())

    def test_packages_signed_exe_and_publishes_post_package_hashes(self):
        self.assertIn("FlamaAudio-Portable-win-x64.zip", self.workflow)
        self.assertIn("Expand-Archive", self.workflow)
        self.assertIn("FlamaAudio-Portable.exe.sha256", self.workflow)
        self.assertIn("FlamaAudio-Portable-win-x64.zip.sha256", self.workflow)
        self.assertIn("gh release create", self.workflow)
        self.assertIn("gh release download", self.workflow)

    def test_deploys_and_reverifies_exact_production_download(self):
        self.assertIn(
            "/var/lib/flama/downloads/FlamaAudio-Portable.exe",
            self.workflow,
        )
        self.assertIn("sha256sum -c FlamaAudio-Portable.exe.sha256", self.workflow)
        self.assertIn("PRODUCTION_DOWNLOAD_URL", self.workflow)
        self.assertIn("Production download did not match", self.workflow)
        self.assertIn("application/x-msdownload", self.workflow)
        self.assertIn("Missing required Flama environment secrets", self.workflow)


if __name__ == "__main__":
    unittest.main()
