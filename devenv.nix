{pkgs, ...}: {
  languages.python = {
    enable = true;
    version = "3.13";
    venv = {
      enable = true;
      requirements = ''
        asyncio
        crc
        cryptography
        filelock
        netifaces
        portalocker ; platform_system == "Windows"
        zeroconf
        pytest
        pytest-benchmark
        -e . # Install this package in edit mode for easy prototyping
      '';
    };
  };
}
