# Design decisions

## Where is the ticket collection stored and how is it passed between functions?
Storage: A plain list of dictionaries that gets passed into functions, which keeps tests easy because there is no hidden global state.

## How does a function signal invalid input (exception or structured error), and how does the CLI display it?
Errors: Raising ValueError with a clear message, and the CLI catches it and prints it.

## What is the expected return value when a ticket is created, assigned, or updated?
Return values: create_ticket returns the new ticket dictionary.

ID generation: Engineer A owns the ID generation. It works after a reload, We derive the next ID from the highest existing numeric ID + 1, not from len(tickets) + 1.

## Which module owns loading/saving JSON and how do other modules call it?
JSON: Storage.py owns loading/saving JSON. Both engineers integrate it.

## How can we test business logic without asking for interactive input inside each test?
We test business logic by using pure functions that take arguments, with no input() inside them. The CLI in main.py is the only place that asks for input.