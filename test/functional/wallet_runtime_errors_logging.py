#!/usr/bin/env python3
# Copyright (c) 2025 The Bitcoin Core developers
# Distributed under the MIT software license, see the accompanying
# file COPYING or http://www.opensource.org/licenses/mit-license.php.
"""Test wallet runtime errors handling logging.

Verifies the error logging in walletdb.cpp for runtime errors.
The test creates a wallet, corrupts the wallet descriptor records, and verifies that loading the wallet
throws a std::runtime_error with a specific error message that can be caught and logged.


"""

import sqlite3
from test_framework.test_framework import BitcoinTestFramework
from test_framework.util import assert_raises_rpc_error

WALLET_DESCRIPTOR = "walletdescriptor"
# Hex prefix '10' + 'walletdescriptor' used to identify descriptor records in wallet database (matches DBKeys::WALLETDESCRIPTOR)
WALLET_DESCRIPTOR_HEX = "10" + WALLET_DESCRIPTOR.encode().hex()

class WalletRuntimeErrorsLoggingTest(BitcoinTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.setup_clean_chain = True
        self.supports_cli = False

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        self.test_wallet_database_corruption()

    def test_wallet_database_corruption(self):
        """Test handling of runtime error messages for corrupted wallets"""
        self.log.info("Test runtime error handling during wallet loading")
        # Create a wallet
        self.nodes[0].createwallet(wallet_name="runtime_error_test")
        self.nodes[0].unloadwallet("runtime_error_test")
        
        # Corrupt the wallet database by writing invalid data that will cause a runtime error
        wallet_db = self.nodes[0].wallets_path / "runtime_error_test" / self.wallet_data_filename
        conn = sqlite3.connect(wallet_db)
        with conn:
            # Corrupt the wallet descriptor records
            cursor = conn.execute("UPDATE main SET value = zeroblob(100) WHERE hex(key) LIKE ? || '%'", (WALLET_DESCRIPTOR_HEX,))
            num_corrupted = cursor.rowcount
            self.log.debug(f"Number of records corrupted: {num_corrupted}")
        conn.close()

        # Try to load the wallet and verify it fails with the specific runtime error
        # The error should be caught by walletdb.cpp's catch(std::runtime_error& e) block
        # and converted to a DBErrors::CORRUPT with the error message logged
        error_msg = "Wallet loading failed. Unrecognized descriptor found."
        assert_raises_rpc_error(-4, error_msg, self.nodes[0].loadwallet, "runtime_error_test")

        # Verify the error was logged with the exact message from walletdb.cpp
        self.log.info("Checking that the runtime error was properly logged")
        with open(self.nodes[0].debug_log_path, 'r', encoding='utf-8') as f:
            log_content = f.read()
            expected_error = "Error: Unrecognized descriptor found in wallet runtime_error_test"
            assert expected_error in log_content, f"Expected error message '{expected_error}' not found in debug log"

if __name__ == '__main__':
    WalletRuntimeErrorsLoggingTest(__file__).main() 