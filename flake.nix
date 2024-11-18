{
  description = "nixos-compose";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/24.05";
    flake-utils.url = "github:numtide/flake-utils";
    nix-editor.url = "github:snowfallorg/nix-editor";
    nix-editor.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      nix-editor,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python3pkgs = pkgs.python3Packages;
        pkgs-ne = nix-editor.packages.${system};
        #customOverrides = self: super: {
        # Overrides go here
        #};

        app = python3pkgs.buildPythonPackage rec {
          pname = "nag";
          version = "locale";
          name = "${pname}-${version}";

          src = builtins.filterSource (
            path: type: type != "directory" || baseNameOf path != ".git" || path != "result"
          ) ./.;

          format = "pyproject";
          buildInputs = [ pkgs.poetry ];
          propagatedBuildInputs =
            with python3pkgs;
            [
              poetry-core
              click
            ]
            ++ (with pkgs; [
              nixfmt-rfc-style
              nix-prefetch-git
            ])
            ++ [ pkgs-ne.default ];
        };

        packageName = "nag";
      in
      rec {
        packages = {
          ${packageName} = app;
          # "${packageName}-full" = app.overrideAttrs(attr: rec {
          #   propagatedBuildInputs = attr.propagatedBuildInputs ++ [
          #     pkgs.docker-compose
          #     pkgs.qemu_kvm
          #     pkgs.vde2
          #   ];
          # });
        };

        defaultPackage = self.packages.${system}.${packageName};

        devShells = {
          default =
            let
              pythonEnv = with pkgs.python3Packages; [
                pytest
                click
		            pyparsing
              ];
            in
              pkgs.mkShell {
                packages = with pkgs; [ pre-commit ] ++ pythonEnv;
                buildInputs = [ self.packages.${system}.${packageName} ];
                # inputsFrom = builtins.attrValues self.packages.${system};
                inputsFrom = [ self.packages.${system}.${packageName} ];
              };
        };
      }
    );
}
