{pkgs, ...}: {
  languages.python = {
    enable = true;
    version = "3.10.10";
    venv = {
      enable = true;
      requirements = ''
        asyncio
        crc
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
