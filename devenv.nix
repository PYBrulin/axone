{pkgs, ...}: {
  languages.python = {
    enable = true;
    version = "3.10.10";
    venv = {
      enable = true;
      # TODO: It is not possible to use a pyproject.toml file to specify dependencies. I am putting this on hold for now. Install dependencies manually.
      requirements = ''
        crc
        filelock
        netifaces
        portalocker ; platform_system == "Windows"
        zeroconf
        . # This package
      '';
    };
  };
}
