// Independent native-API oracle; hexadecimal strings avoid any JSON serializer reuse.
#include "Ab3P.h"
#include <fstream>
#include <iomanip>
#include <sstream>
static std::string hex(const std::string &s) {
  std::ostringstream o;
  for (unsigned char c : s) o << std::hex << std::setw(2) << std::setfill('0') << unsigned(c);
  return o.str();
}
int main(int argc, char **argv) {
  if (argc != 2) return 2;
  std::ifstream in(argv[1]); if (!in) return 1;
  iret::Ab3P tool; std::string line; std::vector<iret::AbbrOut> records;
  size_t index=0;
  while (std::getline(in,line)) {
    tool.get_abbrs(line, records);
    std::cout << "ROW " << index++ << '\n';
    for (const auto &r : records)
      std::cout << hex(r.sf) << '\t' << hex(r.lf) << '\t' << hex(r.strat) << '\t'
        << std::setprecision(17) << r.prec << '\t' << r.sf_offset << '\t' << r.lf_offset << '\n';
  }
  return in.eof() ? 0 : 1;
}
