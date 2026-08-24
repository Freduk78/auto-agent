#!/usr/bin/env ruby
# frozen_string_literal: true

# Parse repository YAML without permitting object deserialization or aliases.
require "yaml"

root = File.expand_path("../..", __dir__)
errors = []
Dir.glob(File.join(root, "**", "*.{yml,yaml}"), File::FNM_EXTGLOB).sort.each do |path|
  next if path.include?("/.git/")

  begin
    YAML.safe_load(File.read(path), permitted_classes: [], aliases: false)
  rescue Psych::Exception, Errno::ENOENT, EncodingError => error
    errors << "#{path.delete_prefix("#{root}/")}: #{error.message}"
  end
end

if errors.empty?
  puts "YAML: valid"
  exit 0
end

warn errors.join("\n")
exit 1
