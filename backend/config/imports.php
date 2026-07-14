<?php

return [
    // The scheduler should provide a freshly exported CSV from 1C. This command only stages data;
    // publishing to a regional site remains a reviewed, separate action.
    'one_c_csv_path' => env('ONE_C_CSV_PATH'),
];
