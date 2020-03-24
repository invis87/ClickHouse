#pragma once

#include <Core/NamesAndTypes.h>
#include <Core/Names.h>
#include <Core/Block.h>
#include <Common/Exception.h>
#include <Storages/ColumnDefault.h>
#include <Storages/ColumnCodec.h>
#include <optional>

#include <boost/multi_index_container.hpp>
#include <boost/multi_index/sequenced_index.hpp>
#include <boost/multi_index/ordered_index.hpp>
#include <boost/multi_index/member.hpp>


namespace DB
{

namespace ErrorCodes
{
    extern const int LOGICAL_ERROR;
}


/// Description of a single table column (in CREATE TABLE for example).
struct ColumnDescription
{
    String name;
    DataTypePtr type;
    ColumnDefault default_desc;
    String comment;
    CompressionCodecPtr codec;
    ASTPtr ttl;
    bool is_virtual = false;

    ColumnDescription() = default;
    ColumnDescription(String name_, DataTypePtr type_, bool is_virtual_);

    bool operator==(const ColumnDescription & other) const;
    bool operator!=(const ColumnDescription & other) const { return !(*this == other); }

    void writeText(WriteBuffer & buf) const;
    void readText(ReadBuffer & buf);
};


/// Description of multiple table columns (in CREATE TABLE for example).
class ColumnsDescription
{
public:
    ColumnsDescription() = default;
    explicit ColumnsDescription(NamesAndTypesList ordinary_, bool all_virtuals = false);

    /// `after_column` can be a Nested column name;
    void add(ColumnDescription column, const String & after_column = String());
    /// `column_name` can be a Nested column name;
    void remove(const String & column_name);

    /// TODO(alesap)
    void rename(const String & column_from, const String & column_to);

    void flattenNested(); /// TODO: remove, insert already flattened Nested columns.

    bool operator==(const ColumnsDescription & other) const { return columns == other.columns; }
    bool operator!=(const ColumnsDescription & other) const { return !(*this == other); }

    auto begin() const { return columns.begin(); }
    auto end() const { return columns.end(); }

    NamesAndTypesList getOrdinary() const;
    NamesAndTypesList getMaterialized() const;
    NamesAndTypesList getAliases() const;
    NamesAndTypesList getVirtuals() const;
    NamesAndTypesList getAllPhysical() const; /// ordinary + materialized.
    NamesAndTypesList getAll() const; /// ordinary + materialized + aliases + virtuals.

    using ColumnTTLs = std::unordered_map<String, ASTPtr>;
    ColumnTTLs getColumnTTLs() const;

    bool has(const String & column_name) const;
    bool hasNested(const String & column_name) const;
    const ColumnDescription & get(const String & column_name) const;

    template <typename F>
    void modify(const String & column_name, F && f)
    {
        auto it = columns.get<1>().find(column_name);
        if (it == columns.get<1>().end())
            throw Exception("Cannot find column " + column_name + " in ColumnsDescription", ErrorCodes::LOGICAL_ERROR);
        if (!columns.get<1>().modify(it, std::forward<F>(f)))
            throw Exception("Cannot modify ColumnDescription for column " + column_name + ": column name cannot be changed", ErrorCodes::LOGICAL_ERROR);
    }

    Names getNamesOfPhysical() const;
    bool hasPhysical(const String & column_name) const;
    NameAndTypePair getPhysical(const String & column_name) const;

    ColumnDefaults getDefaults() const; /// TODO: remove
    bool hasDefault(const String & column_name) const;
    std::optional<ColumnDefault> getDefault(const String & column_name) const;

    CompressionCodecPtr getCodecOrDefault(const String & column_name, CompressionCodecPtr default_codec) const;
    CompressionCodecPtr getCodecOrDefault(const String & column_name) const;

    String toString() const;
    static ColumnsDescription parse(const String & str);

    /// Keep the sequence of columns and allow to lookup by name.
    using Container = boost::multi_index_container<
        ColumnDescription,
        boost::multi_index::indexed_by<
            boost::multi_index::sequenced<>,
            boost::multi_index::ordered_unique<boost::multi_index::member<ColumnDescription, String, &ColumnDescription::name>>>>;

private:
    Container columns;
};

/// Validate default expressions and corresponding types compatibility, i.e.
/// default expression result can be casted to column_type. Also checks, that we
/// don't have strange constructions in default expression like SELECT query or
/// arrayJoin function.
Block validateColumnsDefaultsAndGetSampleBlock(ASTPtr default_expr_list, const NamesAndTypesList & all_columns, const Context & context);
}
