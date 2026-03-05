import pandas as pd


class GeckoPoolAnalyzer:
    def __init__(self,
                 input_file: str = "geckoterminal_high_activity_pools.csv",
                 output_file: str = "geckoterminal_high_activity_pools_clean_sorted.csv"):
        self.input_file = input_file
        self.output_file = output_file
        
        # Columns to keep in final output (in this order)
        self.final_columns = [
            'volume_tvl_ratio',
            'name',
            'network',
            'dex',
            'liquidity_usd',
            'volume_h24_usd',
            'daily_tx',
            'buys_24h',
            'sells_24h',
            'url',
            'pool_address'
        ]

    def run(self) -> None:
        """Main execution flow: load → process → save"""
        df = self._load_data()
        df = self._prepare_numeric_columns(df)
        df = self._calculate_ratio(df)
        df = self._sort_by_ratio(df)
        df = self._select_final_columns(df)
        self._save_result(df)
        self._print_summary(df)

    def _load_data(self) -> pd.DataFrame:
        return pd.read_csv(self.input_file)

    def _prepare_numeric_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in ['liquidity_usd', 'volume_h24_usd']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df

    def _calculate_ratio(self, df: pd.DataFrame) -> pd.DataFrame:
        # Avoid division by zero or very small liquidity → NaN
        df['volume_tvl_ratio'] = df['volume_h24_usd'] / df['liquidity_usd']
        df['volume_tvl_ratio'] = df['volume_tvl_ratio'].where(df['liquidity_usd'] > 0)
        # Round for cleaner CSV
        df['volume_tvl_ratio'] = df['volume_tvl_ratio'].round(4)
        return df

    def _sort_by_ratio(self, df: pd.DataFrame) -> pd.DataFrame:
        return df.sort_values('volume_tvl_ratio', ascending=False)

    def _select_final_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        # Only keep columns that actually exist in the data
        available_cols = [col for col in self.final_columns if col in df.columns]
        return df[available_cols]

    def _save_result(self, df: pd.DataFrame) -> None:
        df.to_csv(self.output_file, index=False)

    def _print_summary(self, df: pd.DataFrame) -> None:
        print(f"Saved: {self.output_file}")
        print(f"Rows: {len(df)}")


if __name__ == "__main__":
    analyzer = GeckoPoolAnalyzer()
    analyzer.run()
