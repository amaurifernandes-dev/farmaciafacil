-- Usuário que a aplicação usa. Não é dono das tabelas, então o RLS vale para ele.
CREATE ROLE ff_app LOGIN PASSWORD 'ff_app';
CREATE DATABASE farmaciafacil_test OWNER ff_owner;
