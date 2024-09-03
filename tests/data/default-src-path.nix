{ lib, stdenv, fetchFromGitLab, openmpi-dynres, autoconf, automake
} :

stdenv.mkDerivation rec {
  pname = "dyn_psets";
  version = "0.0.0";

  src = top/pot.tgz;
  
  nativeBuildInputs = [
    openmpi-dynres
    autoconf
    automake
  ];
  
  preConfigure = ''
    ./autogen.sh
  '';

  meta = with lib; {
    description = "Time-X EuroHPC project: dyn_psets";
    homepage = "";
    #license = licenses.bsd3;
    #maintainers = [ maintainers.markuskowa ];
    platforms = platforms.linux;
  };
}
