// Thin protocol adapter; recognition and candidate selection remain in Ab3P.
#include "Ab3P.h"
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <locale>
#include <cmath>

static std::string quote(const std::string &s) {
  std::ostringstream out;
  out << '"';
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') out << '\\' << c;
    else if (c < 0x20) out << "\\u00" << std::hex << std::setw(2)
                           << std::setfill('0') << static_cast<unsigned>(c) << std::dec;
    else out << c;
  }
  out << '"';
  return out.str();
}

int main(int argc, char **argv) {
  // Retain the protocol stream while redirecting native C++ diagnostics.
  std::ostream protocol(std::cout.rdbuf());
  protocol.imbue(std::locale::classic());
  std::cout.rdbuf(std::cerr.rdbuf());
  if (argc != 2) { std::cerr << "Usage: identify_abbr_jsonl INPUT_TEXT\n"; return 2; }
  try {
    std::ifstream input(argv[1], std::ios::binary);
    if (!input) throw std::runtime_error("Cannot open input");
    // Check all lines before passing any C strings to the native library.
    std::string line;
    while (std::getline(input, line))
      if (line.find('\0') != std::string::npos) throw std::runtime_error("NUL in input");
    if (!input.eof()) throw std::runtime_error("Input read failed");
    input.clear(); input.seekg(0);
    if (!input) throw std::runtime_error("Input rewind failed");
    iret::Ab3P ab3p;
    std::vector<iret::AbbrOut> records;
    size_t index = 0;
    while (std::getline(input, line)) {
      ab3p.get_abbrs(line, records);
      std::ostringstream row;
      row.imbue(std::locale::classic());
      row << std::setprecision(17) << "{\"schema_version\":1,\"line_index\":" << index++ << ",\"records\":[";
      for (size_t i = 0; i < records.size(); ++i) {
        const iret::AbbrOut &r = records[i];
        if (!std::isfinite(r.prec)) throw std::runtime_error("Nonfinite native precision");
        if (i) row << ',';
        row << "{\"sf\":" << quote(r.sf) << ",\"lf\":" << quote(r.lf)
            << ",\"pseudo_precision\":" << r.prec << ",\"strategy\":" << quote(r.strat)
            << ",\"tool_sf_byte_offset\":" << r.sf_offset
            << ",\"tool_lf_byte_offset\":" << r.lf_offset << '}';
      }
      row << "]}\n";
      protocol << row.str(); protocol.flush();
      if (!protocol) throw std::runtime_error("Output write failed");
    }
    if (!input.eof()) throw std::runtime_error("Input read failed");
    return 0;
  } catch (const std::exception &error) {
    std::cerr << error.what() << '\n'; return 1;
  }
}
